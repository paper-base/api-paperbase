from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.core.tenancy import get_active_store

from .service import get_shipping_options


class ShippingOptionsView(APIView):
    """
    GET ?zone_public_id=szn_xxx&order_total=99.00
    Returns available shipping methods and estimated price for the given zone and order total.
    """
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True
    access_scope = "storefront"

    def get(self, request):
        ctx = get_active_store(request)
        store = ctx.store
        if not store:
            return Response([], status=200)

        zone_public_id = (request.query_params.get("zone_public_id") or "").strip()
        if not zone_public_id:
            return Response({"detail": "zone_public_id is required."}, status=400)

        order_total_str = request.query_params.get("order_total")
        data = get_shipping_options(store, zone_public_id, order_total_str)
        return Response(data)
