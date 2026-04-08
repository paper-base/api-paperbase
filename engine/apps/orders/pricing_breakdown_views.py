"""Full-cart storefront pricing (merchandise subtotal + shipping)."""

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.products.models import Product
from engine.apps.products.variant_utils import resolve_storefront_variant, unit_price_for_line
from engine.apps.shipping.models import ShippingMethod, ShippingZone
from engine.core.tenancy import require_api_key_store

from .pricing import PricingEngine, storefront_pricing_breakdown_response


class PricingBreakdownView(APIView):
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True

    def post(self, request):
        store = require_api_key_store(request)
        items = request.data.get("items") or []
        if not isinstance(items, list) or not items:
            return Response({"items": "At least one item is required."}, status=status.HTTP_400_BAD_REQUEST)
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
                {"product": product, "quantity": quantity, "unit_price": unit_price}
            )

        shipping_zone_public_id = (request.data.get("shipping_zone_public_id") or "").strip()
        shipping_method_public_id = (request.data.get("shipping_method_public_id") or "").strip()
        if not shipping_zone_public_id:
            return Response(
                {"shipping_zone_public_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        zone = ShippingZone.objects.filter(store=store, public_id=shipping_zone_public_id, is_active=True).first()
        if zone is None:
            return Response(
                {"shipping_zone_public_id": "Invalid or inactive shipping zone."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        method = None
        if shipping_method_public_id:
            method = ShippingMethod.objects.filter(
                store=store, public_id=shipping_method_public_id, is_active=True
            ).first()

        breakdown = PricingEngine.compute(
            store=store,
            lines=pricing_lines,
            shipping_zone_pk=zone.id,
            shipping_method_pk=method.id if method else None,
        )
        return Response(
            storefront_pricing_breakdown_response(breakdown),
            status=status.HTTP_200_OK,
        )
