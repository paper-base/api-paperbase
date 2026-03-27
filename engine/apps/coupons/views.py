from decimal import Decimal

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.core.tenancy import require_api_key_store

from .services import validate_coupon_for_subtotal


class CouponApplyInputSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)

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
        quote = validate_coupon_for_subtotal(
            store=store,
            code=serializer.validated_data["code"],
            subtotal=serializer.validated_data["subtotal"],
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
