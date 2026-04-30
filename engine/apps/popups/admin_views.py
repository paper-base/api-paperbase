from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.models import ActivityLog
from engine.core.tenancy import get_active_store

from .models import StorePopup
from . import popup_service
from .serializers import StorePopupSerializer, StorePopupWriteSerializer


class AdminStorePopupViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    """
    Admin CRUD for the store popup.

    `GET` is overridden to return the store's current popup for editor convenience
    (active first, otherwise most recent), even when inactive.
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = StorePopup.objects.prefetch_related("images").all()
    lookup_field = "public_id"
    # The dashboard editor expects direct popup JSON (no list pagination wrapper).

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        return qs.filter(store=ctx.store).prefetch_related("images")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return StorePopupSerializer
        return StorePopupWriteSerializer

    def list(self, request, *args, **kwargs):
        ctx = get_active_store(self.request)
        if not ctx.store:
            return Response(None)
        popup = popup_service.get_popup(ctx.store)
        if popup is None:
            return Response(None)
        return Response(
            StorePopupSerializer(popup, context={"request": request}).data
        )

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError({"detail": "No active store resolved."})
        instance = serializer.save(store=store)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="popup",
            entity_id=instance.public_id,
            summary=f"Popup created: {instance.title or instance.public_id}",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        ctx = get_active_store(self.request)
        store = ctx.store
        if store:
            log_activity(
                request=self.request,
                action=ActivityLog.Action.UPDATE,
                entity_type="popup",
                entity_id=instance.public_id,
                summary=f"Popup updated: {instance.title or instance.public_id}",
            )

    def destroy(self, request, *args, **kwargs):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError({"detail": "No active store resolved."})

        instance = self.get_object()
        popup_service.delete_popup(store=store, public_id=instance.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="popup",
            entity_id=instance.public_id,
            summary=f"Popup deleted: {instance.title or instance.public_id}",
        )
        return Response(status=204)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"images/(?P<image_public_id>[^/.]+)",
    )
    def delete_image(self, request, *args, **kwargs):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError({"detail": "No active store resolved."})

        # When lookup_field is "public_id", DRF includes it in kwargs under that name.
        popup_public_id = kwargs.get("public_id") or kwargs.get(self.lookup_field)
        image_public_id = kwargs.get("image_public_id")

        if not popup_public_id or not image_public_id:
            raise ValidationError({"detail": "Missing popup/image public IDs."})

        popup_service.delete_popup_image(
            store=store,
            popup_public_id=str(popup_public_id),
            image_public_id=str(image_public_id),
        )

        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="popupimage",
            entity_id=str(image_public_id),
            summary=f"Popup image deleted: {image_public_id}",
        )
        return Response(status=204)

