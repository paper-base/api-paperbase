from decimal import Decimal

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.orders.pricing import PricingEngine
from engine.apps.products.models import Product
from engine.apps.products.variant_utils import resolve_storefront_variant, unit_price_for_line
from engine.apps.shipping.models import ShippingMethod, ShippingZone
from engine.core.tenancy import require_api_key_store

from .services import resolve_customer_identity, validate_coupon_for_subtotal


class CouponApplyInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate_subtotal(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Subtotal must be greater than zero.")
        return value


class CouponApplyView(APIView):
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True

    def post(self, request):
        store = require_api_key_store(request)
        serializer = CouponApplyInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone, email = resolve_customer_identity(request, serializer.validated_data)
        quote = validate_coupon_for_subtotal(
            store=store,
            code=serializer.validated_data["code"],
            subtotal=serializer.validated_data["subtotal"],
            phone=phone,
            email=email,
        )
        return Response(
            {
                "coupon_public_id": quote.coupon.public_id,
                "code": quote.coupon.code,
                "discount_type": quote.coupon.discount_type,
                "discount_value": quote.coupon.discount_value,
                "discount_amount": quote.discount_amount,
                "subtotal": serializer.validated_data["subtotal"],
                "subtotal_after_discount": serializer.validated_data["subtotal"] - quote.discount_amount,
            },
            status=status.HTTP_200_OK,
        )


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
        zone = ShippingZone.objects.filter(store=store, public_id=shipping_zone_public_id, is_active=True).first()
        method = None
        if shipping_method_public_id:
            method = ShippingMethod.objects.filter(
                store=store, public_id=shipping_method_public_id, is_active=True
            ).first()

        phone, email = resolve_customer_identity(request, request.data)
        breakdown = PricingEngine.compute(
            store=store,
            lines=pricing_lines,
            coupon_code=(request.data.get("coupon_code") or "").strip(),
            coupon_phone=phone,
            coupon_email=email,
            shipping_zone_id=zone.id if zone else None,
            shipping_method_id=method.id if method else None,
        )
        applied_rules = []
        for line in breakdown.lines:
            if line.bulk_rule_public_id:
                applied_rules.append(line.bulk_rule_public_id)
        if breakdown.coupon:
            applied_rules.append(breakdown.coupon.public_id)
        return Response(
            {
                "base_subtotal": breakdown.base_subtotal,
                "bulk_discount_total": breakdown.bulk_discount_total,
                "subtotal_after_bulk": breakdown.subtotal_after_bulk,
                "coupon_discount": breakdown.coupon_discount,
                "subtotal_after_coupon": breakdown.subtotal_after_coupon,
                "shipping_cost": breakdown.shipping_cost,
                "final_total": breakdown.final_total,
                "applied_rules": applied_rules,
                "lines": [
                    {
                        "product_public_id": pl.product_id,
                        "quantity": pl.quantity,
                        "unit_price": str(pl.unit_price),
                        "line_subtotal": str(pl.line_subtotal),
                        "bulk_rule_public_id": pl.bulk_rule_public_id,
                        "bulk_discount_amount": str(pl.bulk_discount_amount),
                    }
                    for pl in breakdown.lines
                ],
            },
            status=status.HTTP_200_OK,
        )
