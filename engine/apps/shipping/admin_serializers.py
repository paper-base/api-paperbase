from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from .models import ShippingZone, ShippingMethod, ShippingRate


class AdminShippingZoneSerializer(SafeModelSerializer):
    class Meta:
        model = ShippingZone
        fields = [
            "public_id",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]


class AdminShippingMethodSerializer(SafeModelSerializer):
    zone_public_ids = serializers.SlugRelatedField(
        many=True,
        required=False,
        slug_field="public_id",
        queryset=ShippingZone.objects.all(),
        source="zones",
    )

    class Meta:
        model = ShippingMethod
        fields = [
            "public_id",
            "name",
            "method_type",
            "is_active",
            "order",
            "zone_public_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]


class AdminShippingRateSerializer(SafeModelSerializer):
    shipping_method_public_id = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=ShippingMethod.objects.all(),
        source="shipping_method",
    )
    shipping_zone_public_id = serializers.SlugRelatedField(
        slug_field="public_id",
        queryset=ShippingZone.objects.all(),
        source="shipping_zone",
    )

    class Meta:
        model = ShippingRate
        fields = [
            "public_id",
            "shipping_method_public_id",
            "shipping_zone_public_id",
            "rate_type",
            "min_order_total",
            "max_order_total",
            "price",
            "is_active",
        ]
        read_only_fields = ["public_id"]

