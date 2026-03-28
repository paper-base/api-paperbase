import logging
from datetime import timedelta

import requests as http_requests
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.models import ActivityLog
from engine.core.tenancy import get_active_store
from engine.apps.emails.triggers import (
    notify_customer_order_confirmation_send_to_courier,
    notify_store_new_order,
    should_send_customer_confirmation_order_email,
)
from engine.apps.couriers.status_mapping import courier_status_implies_order_confirmed
from engine.apps.products.models import Product
from engine.apps.products.variant_utils import resolve_storefront_variant, unit_price_for_line
from engine.apps.shipping.models import ShippingMethod, ShippingZone

from .models import Order
from .pricing import PricingEngine, storefront_pricing_breakdown_response
from .services import (
    get_allowed_next_order_statuses,
    transition_order_status,
)
from .admin_serializers import (
    AdminOrderListSerializer,
    AdminOrderSerializer,
    AdminOrderCreateSerializer,
    AdminOrderUpdateSerializer,
)

logger = logging.getLogger(__name__)

ALLOWED_ORDER_STATUSES = {
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.FAILED,
    Order.Status.CANCELLED,
    Order.Status.RETURNED,
}


class AdminOrderViewSet(
    StoreRolePermissionMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Order.objects.select_related(
        "customer", "user", "shipping_zone", "shipping_method", "shipping_rate"
    ).prefetch_related('items__product').all()
    lookup_field = 'public_id'

    def _send_customer_confirmation_if_enabled(self, order: Order) -> None:
        """
        Send ORDER_CONFIRMED mail exactly once when order reaches confirmed.
        """
        if order.status != Order.Status.CONFIRMED:
            return
        if order.customer_confirmation_sent_at is not None:
            return
        if should_send_customer_confirmation_order_email(order):
            if not notify_customer_order_confirmation_send_to_courier(order):
                raise ValidationError({"detail": "Unable to queue customer confirmation email."})
            order.customer_confirmation_sent_at = timezone.now()
            order.save(update_fields=["customer_confirmation_sent_at"])

    def get_serializer_class(self):
        if self.action == "create":
            return AdminOrderCreateSerializer
        if self.action == 'list':
            return AdminOrderListSerializer
        if self.action in ("update", "partial_update"):
            return AdminOrderUpdateSerializer
        return AdminOrderSerializer

    @action(detail=False, methods=["post"], url_path="pricing-preview")
    def pricing_preview(self, request):
        ctx = get_active_store(request)
        if not ctx.store:
            return Response({"detail": "No active store."}, status=status.HTTP_403_FORBIDDEN)
        items = request.data.get("items") or []
        if not isinstance(items, list) or not items:
            return Response({"items": "At least one item is required."}, status=status.HTTP_400_BAD_REQUEST)
        product_public_ids = [str(item.get("product_public_id", "")).strip() for item in items]
        products = {
            p.public_id: p
            for p in Product.objects.filter(
                store=ctx.store,
                public_id__in=product_public_ids,
                is_active=True,
                status=Product.Status.ACTIVE,
            ).select_related("category", "category__parent")
        }
        pricing_lines = []
        for item in items:
            public_id = str(item.get("product_public_id", "")).strip()
            quantity = int(item.get("quantity") or 0)
            product = products.get(public_id)
            if not product or quantity <= 0:
                return Response({"items": "Invalid product_public_id or quantity."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                variant = resolve_storefront_variant(
                    product=product,
                    variant_public_id=item.get("variant_public_id"),
                )
            except serializers.ValidationError as exc:
                return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
            unit_price = unit_price_for_line(product, variant)
            pricing_lines.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "unit_price": unit_price,
                }
            )
        shipping_zone_public_id = (request.data.get("shipping_zone_public_id") or "").strip()
        shipping_method_public_id = (request.data.get("shipping_method_public_id") or "").strip()
        zone = ShippingZone.objects.filter(
            store=ctx.store,
            public_id=shipping_zone_public_id,
            is_active=True,
        ).first()
        method = None
        if shipping_method_public_id:
            method = ShippingMethod.objects.filter(
                store=ctx.store,
                public_id=shipping_method_public_id,
                is_active=True,
            ).first()

        breakdown = PricingEngine.compute(
            store=ctx.store,
            lines=pricing_lines,
            shipping_zone_pk=zone.id if zone else None,
            shipping_method_pk=method.id if method else None,
        )
        return Response(
            storefront_pricing_breakdown_response(breakdown),
            status=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        """
        Use AdminOrderUpdateSerializer for validation/write, but always respond with AdminOrderSerializer.

        This avoids response serialization errors (items are write-only in update serializer).
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = AdminOrderUpdateSerializer(
            instance,
            data=request.data,
            partial=partial,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance.refresh_from_db()
        return Response(AdminOrderSerializer(instance).data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(store=ctx.store)

        status_value = (self.request.query_params.get("status") or "").strip().lower()
        if status_value in ALLOWED_ORDER_STATUSES:
            qs = qs.filter(status=status_value)

        date_range = (self.request.query_params.get("date_range") or "").strip().lower()
        if date_range == "today":
            qs = qs.filter(created_at__date=timezone.localdate())
        elif date_range == "last_7_days":
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif date_range == "last_30_days":
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=30))

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search)
                | Q(public_id__icontains=search)
                | Q(shipping_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
                | Q(customer__name__icontains=search)
            )

        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        ctx = get_active_store(self.request)
        context["active_store"] = ctx.store
        return context

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError(
                {
                    "detail": (
                        "No active store resolved. Re-login, switch store, or send the "
                        "X-Store-ID header."
                    )
                }
            )
        instance = serializer.save(store=store)
        notify_store_new_order(instance)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="order",
            entity_id=instance.public_id,
            summary=f"Order created: {instance.order_number}",
        )

    @action(detail=True, methods=['patch'], url_path='tracking')
    def update_tracking(self, request, public_id=None):
        order = self.get_object()
        prev_tracking = order.tracking_number
        tracking = request.data.get('tracking_number', '')
        order.tracking_number = tracking
        order.save(update_fields=['tracking_number'])
        if (prev_tracking or "") != (tracking or ""):
            log_activity(
                request=request,
                action=ActivityLog.Action.CUSTOM,
                entity_type="order",
                entity_id=order.public_id,
                summary=f"Order {order.order_number} tracking updated",
                metadata={"from": prev_tracking or "", "to": tracking or ""},
            )
        return Response(AdminOrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="send-to-courier")
    def send_to_courier(self, request, public_id=None):
        order = self.get_object()

        if order.sent_to_courier:
            raise ValidationError({"detail": "This order has already been sent to a courier."})

        if not order.phone:
            raise ValidationError({"detail": "Order phone number is required for courier dispatch."})
        if not order.shipping_address:
            raise ValidationError({"detail": "Shipping address is required for courier dispatch."})

        if not (order.email or "").strip() and should_send_customer_confirmation_order_email(order):
            raise ValidationError(
                {
                    "detail": (
                        "Customer email is required to send order confirmation before courier dispatch."
                    )
                }
            )

        from engine.apps.couriers.models import Courier

        ctx = get_active_store(request)
        courier = Courier.objects.filter(store=ctx.store, is_active=True).first()
        if not courier:
            raise ValidationError({"detail": "No active courier configured for this store."})

        if courier.provider == Courier.Provider.PATHAO:
            from engine.apps.couriers.services import pathao_service as svc
        elif courier.provider == Courier.Provider.STEADFAST:
            from engine.apps.couriers.services import steadfast_service as svc
        else:
            raise ValidationError({"detail": f"Unsupported courier provider: {courier.provider}"})

        if order.status == Order.Status.PENDING:
            order = transition_order_status(
                order=order,
                to_status=Order.Status.CONFIRMED,
                note="Order sent to courier",
                actor_label="system",
            )
        self._send_customer_confirmation_if_enabled(order)

        try:
            result = svc.create_order(order, courier)
        except http_requests.HTTPError as exc:
            logger.exception("Courier API error for order %s", order.order_number)
            raise ValidationError(
                {"detail": f"Courier API error: {exc.response.text if exc.response else str(exc)}"}
            )
        except Exception as exc:
            logger.exception("Unexpected courier error for order %s", order.order_number)
            raise ValidationError({"detail": f"Courier error: {str(exc)}"})

        order.courier_provider = courier.provider
        order.courier_consignment_id = result.get("consignment_id", "")
        order.courier_tracking_code = result.get("tracking_code", "")
        order.courier_status = result.get("status", "")
        order.sent_to_courier = True
        order.save(update_fields=[
            "courier_provider",
            "courier_consignment_id",
            "courier_tracking_code",
            "courier_status",
            "sent_to_courier",
        ])

        log_activity(
            request=request,
            action=ActivityLog.Action.CUSTOM,
            entity_type="order",
            entity_id=order.public_id,
            summary=f"Order {order.order_number} sent to {courier.get_provider_display()}",
            metadata={
                "courier_provider": courier.provider,
                "consignment_id": order.courier_consignment_id,
            },
        )
        return Response(AdminOrderSerializer(order).data)

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, public_id=None):
        order = self.get_object()
        next_status = (request.data.get("status") or "").strip().lower()
        note = (request.data.get("note") or "").strip()
        if not next_status:
            raise ValidationError({"status": "This field is required."})
        try:
            order = transition_order_status(
                order=order,
                to_status=next_status,
                note=note,
                actor_label=f"user:{getattr(request.user, 'public_id', request.user.pk)}",
            )
        except DjangoValidationError as exc:
            raise ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)}
            )
        self._send_customer_confirmation_if_enabled(order)
        log_activity(
            request=request,
            action=ActivityLog.Action.CUSTOM,
            entity_type="order",
            entity_id=order.public_id,
            summary=f"Order {order.order_number} status updated",
            metadata={
                "status": order.status,
                "allowed_next_statuses": get_allowed_next_order_statuses(order.status),
            },
        )
        return Response(
            {
                "order": AdminOrderSerializer(order).data,
                "allowed_next_statuses": get_allowed_next_order_statuses(order.status),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="track")
    def track(self, request, public_id=None):
        order = self.get_object()

        if not order.sent_to_courier or not order.courier_provider:
            raise ValidationError({"detail": "This order has not been sent to a courier."})

        from engine.apps.couriers.models import Courier

        ctx = get_active_store(request)
        courier = Courier.objects.filter(
            store=ctx.store,
            provider=order.courier_provider,
            is_active=True,
        ).first()
        if not courier:
            raise ValidationError({"detail": "No active courier found for this order's provider."})

        if courier.provider == Courier.Provider.PATHAO:
            from engine.apps.couriers.services import pathao_service as svc
        elif courier.provider == Courier.Provider.STEADFAST:
            from engine.apps.couriers.services import steadfast_service as svc
        else:
            raise ValidationError({"detail": f"Unsupported courier provider: {courier.provider}"})

        try:
            result = svc.track_order(order, courier)
        except http_requests.HTTPError as exc:
            logger.exception("Courier tracking error for order %s", order.order_number)
            raise ValidationError(
                {"detail": f"Courier tracking error: {exc.response.text if exc.response else str(exc)}"}
            )
        except Exception as exc:
            logger.exception("Unexpected tracking error for order %s", order.order_number)
            raise ValidationError({"detail": f"Tracking error: {str(exc)}"})

        new_status = result.get("status", order.courier_status)
        update_fields = []
        if new_status and new_status != order.courier_status:
            order.courier_status = new_status
            update_fields.append("courier_status")

        effective = new_status or order.courier_status
        if courier_status_implies_order_confirmed(order.courier_provider, effective):
            if order.status == Order.Status.PENDING:
                prev = order.status
                order = transition_order_status(
                    order=order,
                    to_status=Order.Status.CONFIRMED,
                    note=f"Courier status: {effective}",
                    actor_label="system",
                )
                self._send_customer_confirmation_if_enabled(order)
                log_activity(
                    request=request,
                    action=ActivityLog.Action.CUSTOM,
                    entity_type="order",
                    entity_id=order.public_id,
                    summary=f"Order {order.order_number} confirmed (courier handoff)",
                    metadata={"from": prev, "to": order.status, "courier_status": effective},
                )

        if update_fields:
            order.save(update_fields=update_fields)

        return Response({
            "courier_provider": order.courier_provider,
            "courier_consignment_id": order.courier_consignment_id,
            "courier_tracking_code": order.courier_tracking_code,
            "courier_status": order.courier_status,
            "order_status": order.status,
            "details": result.get("details", {}),
        })

    def perform_destroy(self, instance):
        public_id = instance.public_id
        order_number = getattr(instance, "order_number", "")
        super().perform_destroy(instance)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="order",
            entity_id=public_id,
            summary=f"Order deleted: {order_number}" if order_number else "Order deleted",
        )
