from rest_framework import serializers
from .models import ShippingMethod, ShippingZone, ShippingRate


class ShippingOptionSerializer(serializers.Serializer):
    method_id = serializers.IntegerField()
    method_name = serializers.CharField()
    zone_id = serializers.IntegerField()
    zone_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    rate_type = serializers.CharField()
