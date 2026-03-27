from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import IsDashboardUser
from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.models import ActivityLog
from engine.core.tenancy import get_active_store

from .models import Coupon
from .admin_serializers import AdminCouponSerializer
from .services import validate_coupon_for_subtotal


class AdminCouponViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = AdminCouponSerializer
    queryset = Coupon.objects.all()
    lookup_field = 'public_id'

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        return qs.filter(store=ctx.store)

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValueError("No active store for coupon creation")
        instance = serializer.save(store=store)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="coupon",
            entity_id=instance.public_id,
            summary=f"Coupon created: {instance.code}",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="coupon",
            entity_id=instance.public_id,
            summary=f"Coupon updated: {instance.code}",
        )

    def perform_destroy(self, instance):
        code = instance.code
        public_id = instance.public_id
        super().perform_destroy(instance)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="coupon",
            entity_id=public_id,
            summary=f"Coupon deleted: {code}",
        )

    @action(detail=False, methods=["post"], url_path="apply")
    def apply_coupon(self, request):
        ctx = get_active_store(request)
        if not ctx.store:
            return Response({"detail": "No active store."}, status=status.HTTP_403_FORBIDDEN)
        code = (request.data.get("code") or "").strip()
        try:
            subtotal = serializers.DecimalField(max_digits=12, decimal_places=2).to_internal_value(
                request.data.get("subtotal")
            )
        except Exception:
            return Response({"subtotal": "Invalid subtotal."}, status=status.HTTP_400_BAD_REQUEST)

        quote = validate_coupon_for_subtotal(store=ctx.store, code=code, subtotal=subtotal)
        return Response(
            {
                "coupon_public_id": quote.coupon.public_id,
                "code": quote.coupon.code,
                "discount_type": quote.coupon.discount_type,
                "discount_value": quote.coupon.discount_value,
                "discount_amount": quote.discount_amount,
                "subtotal": subtotal,
                "subtotal_after_discount": subtotal - quote.discount_amount,
            },
            status=status.HTTP_200_OK,
        )
