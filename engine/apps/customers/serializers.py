from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer
from .models import Customer, CustomerAddress


class CustomerAddressSerializer(SafeModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = [
            'public_id', 'label', 'name', 'phone', 'address_line1', 'address_line2',
            'city', 'region', 'postal_code', 'country',
            'is_default_shipping', 'is_default_billing', 'created_at',
        ]
        read_only_fields = ['public_id', 'created_at']


class CustomerProfileSerializer(SafeModelSerializer):
    user_public_id = serializers.CharField(source='user.public_id', read_only=True, allow_null=True)
    addresses = CustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            'user_public_id', 'name', 'phone', 'email', 'address', 'total_orders',
            'marketing_opt_in', 'addresses', 'created_at', 'updated_at',
        ]


class CustomerSerializer(SafeModelSerializer):
    class Meta:
        model = Customer
        fields = ['public_id', 'name', 'phone', 'email', 'address', 'total_orders']
        read_only_fields = ['public_id', 'total_orders']
