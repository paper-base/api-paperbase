from rest_framework import viewsets, mixins
from rest_framework.exceptions import ValidationError

from config.permissions import IsDashboardUser
from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.models import ActivityLog
from engine.core.tenancy import get_active_store
from .admin_serializers import AdminNotificationSerializer, AdminStaffNotificationSerializer
from .models import StaffNotification, StorefrontCTA
from .services import invalidate_notification_cache


class AdminStaffNotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """List/retrieve/update (mark read) staff inbox notifications for admin dashboard."""
    permission_classes = [IsDashboardUser]
    serializer_class = AdminStaffNotificationSerializer
    queryset = StaffNotification.objects.all().order_by('-created_at')
    lookup_field = 'public_id'

    def get_queryset(self):
        ctx = get_active_store(self.request)
        if not ctx.store:
            return super().get_queryset().none()
        return super().get_queryset().filter(
            store=ctx.store,
            user=self.request.user,
        )


class AdminNotificationViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = AdminNotificationSerializer
    queryset = StorefrontCTA.objects.all()
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
            raise ValidationError(
                {
                    "detail": (
                        "No active store resolved. Re-login, switch store, or send the "
                        "X-Store-ID header."
                    )
                }
            )
        instance = serializer.save(store=store)
        invalidate_notification_cache(store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="notification",
            entity_id=instance.public_id,
            summary="Notification created",
            metadata={"text": getattr(instance, "cta_text", "")},
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        ctx = get_active_store(self.request)
        if ctx.store:
            invalidate_notification_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="notification",
            entity_id=instance.public_id,
            summary="Notification updated",
            metadata={"text": getattr(instance, "cta_text", "")},
        )

    def perform_destroy(self, instance):
        public_id = instance.public_id
        text = getattr(instance, "cta_text", "")
        ctx = get_active_store(self.request)
        super().perform_destroy(instance)
        if ctx.store:
            invalidate_notification_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="notification",
            entity_id=public_id,
            summary="Notification deleted",
            metadata={"text": text},
        )
