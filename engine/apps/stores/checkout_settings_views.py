from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import DenyAPIKeyAccess, IsStoreStaff
from engine.core import cache_service
from engine.core.tenancy import get_active_store
from engine.apps.stores.tasks import dispatch_storefront_webhook

from .models import StorefrontCheckoutSettings


def _invalidate_store_public_payload_cache(store_public_id: str) -> None:
    cache_service.delete(f"cache:{store_public_id}:store_public:v1")
    cache_service.delete(f"cache:{store_public_id}:store_public:v3")


class StoreCheckoutSettingsView(APIView):
    """Dashboard GET/PATCH for storefront checkout form variant."""

    permission_classes = [DenyAPIKeyAccess, IsStoreStaff]

    def get(self, request):
        ctx = get_active_store(request)
        store = ctx.store
        if not store:
            return Response({"detail": "No store."}, status=status.HTTP_404_NOT_FOUND)
        row, _ = StorefrontCheckoutSettings.objects.get_or_create(
            store=store,
            defaults={"customer_form_variant": "extended"},
        )
        return Response({"customer_form_variant": row.customer_form_variant})

    def patch(self, request):
        ctx = get_active_store(request)
        store = ctx.store
        if not store:
            return Response({"detail": "No store."}, status=status.HTTP_404_NOT_FOUND)

        body = request.data
        if not isinstance(body, dict):
            return Response(
                {"detail": "Invalid request body."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if set(body.keys()) != {"customer_form_variant"}:
            return Response(
                {"detail": "Only customer_form_variant is allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        value = body.get("customer_form_variant")
        if value not in ("minimal", "extended"):
            return Response(
                {"detail": "customer_form_variant must be minimal or extended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        row, _ = StorefrontCheckoutSettings.objects.get_or_create(
            store=store,
            defaults={"customer_form_variant": "extended"},
        )
        row.customer_form_variant = value
        row.save(update_fields=["customer_form_variant"])
        _invalidate_store_public_payload_cache(store.public_id)
        sid = store.public_id
        if sid:
            dispatch_storefront_webhook.delay(
                sid,
                {"event": "store.updated", "type": "store", "store_public_id": sid},
            )
        return Response({"customer_form_variant": row.customer_form_variant})
