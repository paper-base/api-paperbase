from decimal import Decimal

from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from .models import Customer, CustomerAddress


class AdminCustomerAddressSerializer(SafeModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = [
            "public_id",
            "label",
            "name",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "region",
            "postal_code",
            "country",
            "is_default_shipping",
            "is_default_billing",
            "created_at",
        ]
        read_only_fields = ["public_id", "created_at"]


class AdminCustomerSerializer(SafeModelSerializer):
    user_public_id = serializers.CharField(source="user.public_id", read_only=True, allow_null=True)
    user_email = serializers.CharField(source="user.email", read_only=True, allow_null=True)
    user_username = serializers.SerializerMethodField()
    ledger_order_count = serializers.SerializerMethodField()
    ledger_total_spent = serializers.SerializerMethodField()
    default_shipping_address_public_id = serializers.CharField(
        source="default_shipping_address.public_id", read_only=True, allow_null=True
    )
    default_billing_address_public_id = serializers.CharField(
        source="default_billing_address.public_id", read_only=True, allow_null=True
    )
    addresses = AdminCustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            "public_id",
            "user_public_id",
            "user_email",
            "user_username",
            "name",
            "phone",
            "email",
            "address",
            "total_orders",
            "ledger_order_count",
            "ledger_total_spent",
            "marketing_opt_in",
            "default_shipping_address_public_id",
            "default_billing_address_public_id",
            "addresses",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]

    def get_user_username(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return None
        full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        if full_name:
            return full_name
        return getattr(user, "email", None)

    def get_ledger_order_count(self, obj):
        return int(getattr(obj, "ledger_order_count", 0) or 0)

    def get_ledger_total_spent(self, obj):
        v = getattr(obj, "ledger_total_spent", None)
        if v is None:
            return Decimal("0.00")
        return v if isinstance(v, Decimal) else Decimal(str(v))


class AdminCustomerListSerializer(SafeModelSerializer):
    user_public_id = serializers.CharField(source="user.public_id", read_only=True, allow_null=True)
    user_email = serializers.CharField(source="user.email", read_only=True, allow_null=True)
    user_username = serializers.SerializerMethodField()
    ledger_order_count = serializers.SerializerMethodField()
    ledger_total_spent = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "public_id",
            "user_public_id",
            "user_email",
            "user_username",
            "name",
            "phone",
            "email",
            "address",
            "total_orders",
            "ledger_order_count",
            "ledger_total_spent",
            "marketing_opt_in",
            "created_at",
        ]

    def get_user_username(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return None
        full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        if full_name:
            return full_name
        return getattr(user, "email", None)

    def get_ledger_order_count(self, obj):
        return int(getattr(obj, "ledger_order_count", 0) or 0)

    def get_ledger_total_spent(self, obj):
        v = getattr(obj, "ledger_total_spent", None)
        if v is None:
            return Decimal("0.00")
        return v if isinstance(v, Decimal) else Decimal(str(v))
