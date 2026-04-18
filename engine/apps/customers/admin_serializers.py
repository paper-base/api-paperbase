from decimal import Decimal

from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from .models import Customer
from .services.purchase_service import (
    CONFIRMED_FIRST_AT,
    CONFIRMED_LAST_AT,
    CONFIRMED_ORDER_COUNT,
    CONFIRMED_SPENT,
)


class AdminCustomerSerializer(SafeModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "public_id",
            "name",
            "phone",
            "email",
            "address",
            "total_orders",
            "total_spent",
            "first_order_at",
            "last_order_at",
            "is_repeat_customer",
            "avg_order_interval_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]


class AdminCustomerListSerializer(SafeModelSerializer):
    """
    List response uses confirmed-order annotations (see ``annotate_queryset_list_purchase_metrics``)
    for purchase totals and dates so values match the customer ``details`` endpoint
    and never rely on denormalized rollups alone.
    """

    total_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    first_order_at = serializers.SerializerMethodField()
    last_order_at = serializers.SerializerMethodField()

    def get_total_orders(self, obj):
        if hasattr(obj, CONFIRMED_ORDER_COUNT):
            return int(getattr(obj, CONFIRMED_ORDER_COUNT) or 0)
        return int(obj.total_orders or 0)

    def get_total_spent(self, obj):
        if hasattr(obj, CONFIRMED_SPENT):
            v = getattr(obj, CONFIRMED_SPENT)
            if v is not None and not isinstance(v, Decimal):
                v = Decimal(str(v))
            return v
        return obj.total_spent

    def get_first_order_at(self, obj):
        if hasattr(obj, CONFIRMED_FIRST_AT):
            return getattr(obj, CONFIRMED_FIRST_AT)
        return obj.first_order_at

    def get_last_order_at(self, obj):
        if hasattr(obj, CONFIRMED_LAST_AT):
            return getattr(obj, CONFIRMED_LAST_AT)
        return obj.last_order_at

    class Meta:
        model = Customer
        fields = [
            "public_id",
            "name",
            "phone",
            "email",
            "address",
            "total_orders",
            "total_spent",
            "first_order_at",
            "last_order_at",
            "is_repeat_customer",
            "avg_order_interval_days",
            "created_at",
        ]
