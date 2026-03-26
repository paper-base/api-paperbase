from rest_framework import viewsets

from config.permissions import IsDashboardUser
from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.models import ActivityLog
from engine.core.tenancy import get_active_store

from .models import Review
from .admin_serializers import AdminReviewSerializer
from .services import invalidate_review_cache


class AdminReviewViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = AdminReviewSerializer
    queryset = Review.objects.select_related("product", "user").order_by("-created_at")
    lookup_field = 'public_id'

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        return qs.filter(product__store=ctx.store)

    def perform_update(self, serializer):
        instance = serializer.save()
        ctx = get_active_store(self.request)
        if ctx.store:
            invalidate_review_cache(
                ctx.store.public_id, instance.product.public_id
            )
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="review",
            entity_id=instance.public_id,
            summary=f"Review updated: {instance.product.name} - {instance.rating} stars",
        )

    def perform_destroy(self, instance):
        public_id = instance.public_id
        product_name = instance.product.name
        product_public_id = instance.product.public_id
        ctx = get_active_store(self.request)
        super().perform_destroy(instance)
        if ctx.store:
            invalidate_review_cache(ctx.store.public_id, product_public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="review",
            entity_id=public_id,
            summary=f"Review deleted: {product_name}",
        )
