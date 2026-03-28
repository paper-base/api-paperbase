from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.products.models import Product
from engine.apps.products.variant_utils import resolve_storefront_variant, unit_price_for_line
from engine.core.tenancy import get_active_store, require_api_key_store, require_resolved_store

from .service import (
    build_shipping_zones_catalog,
    get_shipping_options,
    preview_shipping_for_lines,
)


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


class ShippingZonesView(APIView):
    """List shipping zones with delivery estimates and merged cost bands."""

    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True
    access_scope = "storefront"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_resolved_store(request)

    def get(self, request):
        store = require_api_key_store(request)
        return Response(build_shipping_zones_catalog(store))


class ShippingPreviewView(APIView):
    """
    POST { "zone_public_id": "szn_...", "items": [...] }
    Stateless quote using the same pricing engine as checkout (merchandise subtotal + shipping).
    """

    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True
    access_scope = "storefront"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_resolved_store(request)

    def post(self, request):
        store = require_api_key_store(request)
        zone_public_id = (request.data.get("zone_public_id") or "").strip()
        items = request.data.get("items") or []
        if not zone_public_id:
            return Response(
                {"zone_public_id": ["This field is required."]},
                status=400,
            )
        if not isinstance(items, list) or not items:
            return Response({"detail": "items must be a non-empty list."}, status=400)

        product_public_ids = [str(item.get("product_public_id", "")).strip() for item in items]
        products = {
            p.public_id: p
            for p in Product.objects.filter(
                store=store,
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
                return Response(
                    {"detail": "Invalid product_public_id or quantity in items."},
                    status=400,
                )
            try:
                variant = resolve_storefront_variant(
                    product=product,
                    variant_public_id=item.get("variant_public_id"),
                )
            except serializers.ValidationError as exc:
                return Response(exc.detail, status=400)
            unit_price = unit_price_for_line(product, variant)
            pricing_lines.append(
                {"product": product, "quantity": quantity, "unit_price": unit_price}
            )

        try:
            payload = preview_shipping_for_lines(
                store=store, zone_public_id=zone_public_id, lines=pricing_lines
            )
        except ValidationError as exc:
            if hasattr(exc, "message_dict") and exc.message_dict:
                return Response(exc.message_dict, status=400)
            return Response({"detail": list(exc.messages)}, status=400)
        return Response(payload)
