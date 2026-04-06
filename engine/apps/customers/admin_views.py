from decimal import Decimal
from datetime import timedelta

from django.db.models import Count, DecimalField, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import IsDashboardUser
from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.models import ActivityLog
from engine.core.tenancy import get_active_store
from engine.apps.orders.models import Order, PurchaseLedgerEntry

from .models import Customer, CustomerAddress
from .services import get_customer_ledger_analytics
from .admin_serializers import (
    AdminCustomerSerializer,
    AdminCustomerListSerializer,
    AdminCustomerAddressSerializer,
)


class AdminCustomerViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("user").prefetch_related("addresses").all()
    lookup_field = 'public_id'

    def get_serializer_class(self):
        if self.action == "list":
            return AdminCustomerListSerializer
        return AdminCustomerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(store=ctx.store).order_by("-created_at", "id")

        joined_date = (self.request.query_params.get("joined_date") or "").strip().lower()
        if joined_date == "today":
            qs = qs.filter(created_at__date=timezone.localdate())
        elif joined_date == "last_7_days":
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif joined_date == "last_30_days":
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=30))

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )

        # Ledger-based counts for list/retrieve (no N+1). See Customer.total_orders (legacy column).
        count_subq = (
            PurchaseLedgerEntry.objects.filter(
                store_id=OuterRef("store_id"),
                customer_id=OuterRef("pk"),
            )
            .values("customer_id")
            .annotate(c=Count("order_public_id", distinct=True))
            .values("c")[:1]
        )
        sum_subq = (
            PurchaseLedgerEntry.objects.filter(
                store_id=OuterRef("store_id"),
                customer_id=OuterRef("pk"),
            )
            .values("customer_id")
            .annotate(s=Sum("line_total"))
            .values("s")[:1]
        )
        qs = qs.annotate(
            ledger_order_count=Coalesce(
                Subquery(count_subq, output_field=IntegerField()),
                Value(0),
            ),
            ledger_total_spent=Coalesce(
                Subquery(
                    sum_subq,
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
                Value(Decimal("0.00")),
            ),
        )

        return qs

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValueError("No active store for customer creation")
        instance = serializer.save(store=store)
        label = (instance.email or (instance.user.email if instance.user else "") or instance.phone)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="customer",
            entity_id=instance.public_id,
            summary=f"Customer created: {label}",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        label = (instance.email or (instance.user.email if instance.user else "") or instance.phone)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="customer",
            entity_id=instance.public_id,
            summary=f"Customer updated: {label}",
        )

    def perform_destroy(self, instance):
        email = instance.email or (instance.user.email if instance.user else "") or instance.phone
        public_id = instance.public_id
        super().perform_destroy(instance)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="customer",
            entity_id=public_id,
            summary=f"Customer deleted: {email}",
        )

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, public_id=None):
        customer = self.get_object()
        la = get_customer_ledger_analytics(customer)
        total_orders = la.historical_order_count
        total_spent = la.total_spent
        average_order_value = la.average_order_value
        loyalty_score = la.loyalty_score
        # Live orders only — may be empty if all orders were deleted; ledger has no district snapshot.
        latest_district = (
            Order.objects.filter(store=customer.store, customer=customer)
            .exclude(district="")
            .order_by("-created_at")
            .values_list("district", flat=True)
            .first()
        )
        entries = list(
            PurchaseLedgerEntry.objects.filter(
                store=customer.store, customer=customer
            ).order_by("-recorded_at", "-id")
        )
        pids_with_live_order = {e.order_public_id for e in entries if e.order_id}
        status_by_public_id = {}
        if pids_with_live_order:
            status_by_public_id = {
                o.public_id: o.status
                for o in Order.objects.filter(
                    store=customer.store, public_id__in=pids_with_live_order
                ).only("public_id", "status")
            }
        ordered_products = []
        for e in entries:
            ordered_products.append(
                {
                    "order_public_id": e.order_public_id,
                    "order_number": e.order_number,
                    "ordered_at": e.recorded_at,
                    "product_public_id": e.product_public_id or None,
                    "product_name": e.product_name,
                    "variant_label": e.variant_label or None,
                    "quantity": e.quantity,
                    "unit_price": e.unit_price,
                    "current_order_status": status_by_public_id.get(e.order_public_id),
                    "order_status_at_purchase": e.order_status_snapshot,
                }
            )

        payload = {
            "customer": {
                "public_id": customer.public_id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "address": customer.address,
                "district": latest_district,
            },
            "analytics": {
                "total_orders": total_orders,
                "total_spent": total_spent,
                "average_order_value": average_order_value,
                "first_order_date": la.first_purchase_at,
                "last_order_date": la.last_purchase_at,
                "loyalty_score": loyalty_score,
            },
            "ordered_products": ordered_products,
        }
        return Response(payload)


class AdminCustomerAddressViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = AdminCustomerAddressSerializer
    queryset = CustomerAddress.objects.select_related("customer").all()
    lookup_field = 'public_id'

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(customer__store=ctx.store)
        customer_public_id = self.request.query_params.get("customer")
        if customer_public_id:
            qs = qs.filter(customer__public_id=customer_public_id)
        return qs
