"""Single-line storefront pricing preview (PricingEngine — bulk then coupon then shipping)."""

from __future__ import annotations


from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.coupons.services import resolve_customer_identity
from engine.apps.products.models import Product
from engine.apps.products.variant_utils import resolve_storefront_variant, unit_price_for_line
from engine.apps.shipping.models import ShippingMethod, ShippingZone
from engine.core.tenancy import require_api_key_store

from .pricing import PricingEngine


class PricingPreviewInputSerializer(serializers.Serializer):
    """Accept product_public_id or legacy product_id (same value)."""

    product_public_id = serializers.CharField(required=False, allow_blank=True, default="")
    product_id = serializers.CharField(required=False, allow_blank=True, default="")
    variant_public_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    variant_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    quantity = serializers.IntegerField(min_value=1, default=1)
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    shipping_zone_public_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    shipping_method_public_id = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        pid = (attrs.get("product_public_id") or attrs.get("product_id") or "").strip()
        if not pid:
            raise serializers.ValidationError(
                {"product_public_id": "product_public_id or product_id is required."}
            )
        attrs["_product_public_id"] = pid
        v1 = (attrs.get("variant_public_id") or "").strip()
        v2 = (attrs.get("variant_id") or "").strip()
        attrs["_variant_public_id"] = v1 or v2
        return attrs


class PricingPreviewView(APIView):
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
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

        phone, email = resolve_customer_identity(request, request.data)
        breakdown = PricingEngine.compute(
            store=store,
            lines=lines,
            coupon_code=(ser.validated_data.get("coupon_code") or "").strip(),
            coupon_phone=phone,
            coupon_email=email,
            shipping_zone_id=zone.id if zone else None,
            shipping_method_id=method.id if method else None,
        )

        line0 = breakdown.lines[0] if breakdown.lines else None
        applied_rules = []
        if line0 and line0.bulk_rule_public_id:
            applied_rules.append(line0.bulk_rule_public_id)
        if breakdown.coupon:
            applied_rules.append(breakdown.coupon.public_id)

        return Response(
            {
                "product_public_id": product.public_id,
                "variant_public_id": variant.public_id if variant else None,
                "quantity": qty,
                "unit_price": str(unit_price),
                "base_price": str(breakdown.base_subtotal),
                "bulk_discount": str(breakdown.bulk_discount_total),
                "coupon_discount": str(breakdown.coupon_discount),
                "shipping_cost": str(breakdown.shipping_cost),
                "final_price": str(breakdown.final_total),
                "applied_rules": applied_rules,
                "subtotal_after_bulk": str(breakdown.subtotal_after_bulk),
                "subtotal_after_coupon": str(breakdown.subtotal_after_coupon),
            },
            status=status.HTTP_200_OK,
        )
