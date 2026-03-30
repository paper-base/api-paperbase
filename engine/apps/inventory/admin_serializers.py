from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer
from .models import Inventory, StockMovement


class StockMovementSerializer(SafeModelSerializer):
    actor_public_id = serializers.CharField(source='actor.public_id', read_only=True, allow_null=True)

    class Meta:
        model = StockMovement
        fields = [
            'public_id',
            'change',
            'reason',
            'source',
            'reference_id',
            'reference',
            'created_at',
            'actor_public_id',
        ]
        read_only_fields = fields


class InventoryListSerializer(SafeModelSerializer):
    product_public_id = serializers.CharField(source='product.public_id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_public_id = serializers.CharField(source='variant.public_id', read_only=True, allow_null=True)
    variant_sku = serializers.CharField(source='variant.sku', read_only=True, allow_null=True)
    option_labels = serializers.SerializerMethodField(read_only=True)
    is_low = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = [
            'public_id', 'product_public_id', 'product_name', 'variant_public_id', 'variant_sku',
            'option_labels',
            'quantity', 'low_stock_threshold', 'is_tracked', 'updated_at', 'is_low',
        ]

    def get_option_labels(self, obj):
        v = obj.variant
        if v is None:
            return []
        # Ordering comes from AdminInventoryViewSet Prefetch; use .all() to hit cache.
        return [
            f"{link.attribute_value.attribute.name}: {link.attribute_value.value}"
            for link in v.attribute_values.all()
        ]

    def get_is_low(self, obj):
        return obj.is_low_stock()


class InventoryDetailSerializer(InventoryListSerializer):
    movements = StockMovementSerializer(many=True, read_only=True)

    class Meta(InventoryListSerializer.Meta):
        fields = InventoryListSerializer.Meta.fields + ['movements']
