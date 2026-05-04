"""Single-line storefront pricing preview (merchandise subtotal + shipping)."""

from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.products.models import Product
from engine.apps.products.variant_utils import resolve_storefront_variant, unit_price_for_line
from engine.apps.shipping.models import ShippingMethod, ShippingZone
from engine.core.tenancy import require_api_key_store

from .pricing import PricingEngine, storefront_pricing_breakdown_response


class PricingPreviewInputSerializer(serializers.Serializer):
    product_public_id = serializers.CharField(required=True, allow_blank=False)
    variant_public_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    quantity = serializers.IntegerField(min_value=1, default=1)
    shipping_zone_public_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    shipping_method_public_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        pid = str(attrs.get("product_public_id") or "").strip()
        if not pid:
            raise serializers.ValidationError({"product_public_id": "This field is required."})
        attrs["_product_public_id"] = pid
        attrs["_variant_public_id"] = (attrs.get("variant_public_id") or "").strip()
        return attrs


class PricingPreviewView(APIView):
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    throttle_classes = ()
    allow_api_key = True

    def post(self, request):
        store = require_api_key_store(request)
        ser = PricingPreviewInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        product = (
            Product.objects.filter(
                store=store,
                public_id=ser.validated_data["_product_public_id"],
                is_active=True,
                status=Product.Status.ACTIVE,
            )
            .select_related("category", "category__parent")
            .first()
        )
        if not product:
            return Response(
                {"detail": "Product not found or unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            variant = resolve_storefront_variant(
                product=product,
                variant_public_id=ser.validated_data["_variant_public_id"],
            )
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        qty = ser.validated_data["quantity"]
        unit_price = unit_price_for_line(product, variant)
        lines = [{"product": product, "quantity": qty, "unit_price": unit_price}]

        zone = None
        method = None
        zid = (ser.validated_data.get("shipping_zone_public_id") or "").strip()
        mid = (ser.validated_data.get("shipping_method_public_id") or "").strip()
        if zid:
            zone = ShippingZone.objects.filter(
                store=store, public_id=zid, is_active=True
            ).first()
        if mid:
            method = ShippingMethod.objects.filter(
                store=store, public_id=mid, is_active=True
            ).first()

        breakdown = PricingEngine.compute(
            store=store,
            lines=lines,
            shipping_zone_pk=zone.id if zone else None,
            shipping_method_pk=method.id if method else None,
        )

        return Response(
            storefront_pricing_breakdown_response(breakdown),
            status=status.HTTP_200_OK,
        )
