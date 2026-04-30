from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.products.views import StorefrontTenantMixin
from engine.core.tenancy import require_api_key_store

from . import popup_service
from .serializers import StorePopupSerializer


class StorePopupView(StorefrontTenantMixin, APIView):
    """
    Storefront read-only popup endpoint (tenant-scoped via storefront API key).
    Returns `null` when no active popup exists.
    """

    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True
    access_scope = "storefront"

    def get(self, request, *args, **kwargs):
        store = require_api_key_store(request)
        popup = popup_service.get_popup(store)

        if popup is None:
            return Response(None)
        if not popup.is_active:
            return Response(None)

        return Response(
            StorePopupSerializer(popup, context={"request": request}).data
        )

