from rest_framework import serializers


class ShippingOptionSerializer(serializers.Serializer):
    rate_public_id = serializers.CharField()
    method_public_id = serializers.CharField()
    method_name = serializers.CharField()
    method_type = serializers.CharField()
    method_order = serializers.IntegerField()
    zone_public_id = serializers.CharField()
    zone_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    rate_type = serializers.CharField()
    min_order_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True, required=False
    )
    max_order_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True, required=False
    )
