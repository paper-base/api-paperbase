from datetime import date

from rest_framework import mixins, viewsets

from config.permissions import DenyAPIKeyAccess, IsDashboardUser, IsStoreAdmin
from engine.core.tenancy import get_active_store
from .models import ActivityLog
from .admin_serializers import AdminActivityLogSerializer


class StoreRolePermissionMixin:
    """
    Mixin that applies role-based permissions to ViewSet actions.

    - Safe read actions (list, retrieve) → IsDashboardUser (any store staff)
    - Write/destructive actions (create, update, partial_update, destroy,
      and any custom action) → IsStoreAdmin (owner or admin only)

    Subclasses must NOT set `permission_classes` directly; they should call
    `super().get_permissions()` via this mixin instead.
    """

    READ_ACTIONS = {"list", "retrieve", "metadata"}

    def get_permissions(self):
        if self.action in self.READ_ACTIONS:
            return [DenyAPIKeyAccess(), IsDashboardUser()]
        return [DenyAPIKeyAccess(), IsStoreAdmin()]


class AdminActivityLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [DenyAPIKeyAccess, IsDashboardUser]
    serializer_class = AdminActivityLogSerializer
    lookup_field = "public_id"
    queryset = ActivityLog.objects.select_related("actor").all()

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(store=ctx.store)

        params = self.request.query_params

        entity_type = (params.get("entity_type") or "").strip()
        if entity_type:
            qs = qs.filter(entity_type=entity_type)

        action = (params.get("action") or "").strip()
        if action:
            qs = qs.filter(action=action)

        actor = (params.get("actor") or "").strip()
        if actor:
            qs = qs.filter(actor__public_id=actor)

        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(summary__icontains=q)

        start_date = (params.get("start_date") or "").strip()
        if start_date:
            try:
                start = date.fromisoformat(start_date)
                qs = qs.filter(created_at__date__gte=start)
            except ValueError:
                pass

        end_date = (params.get("end_date") or "").strip()
        if end_date:
            try:
                end = date.fromisoformat(end_date)
                qs = qs.filter(created_at__date__lte=end)
            except ValueError:
                pass

        return qs

