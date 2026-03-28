from rest_framework import serializers

from engine.apps.products.serializers import ProductListSerializer
from engine.apps.shipping.models import ShippingMethod, ShippingZone

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    variant_public_id = serializers.SerializerMethodField()
    variant_options = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'public_id',
            'product',
            'product_name',
            'status',
            'quantity',
            'price',
            'variant_public_id',
            'variant_options',
        ]
        read_only_fields = ['public_id']

    def get_product(self, obj):
        if not obj.product:
            return None
        return ProductListSerializer(obj.product, context=self.context).data

    def get_product_name(self, obj):
        return obj.product.name if obj.product else "Unavailable"

    def get_status(self, obj):
        return "active" if obj.product else "deleted"

    def get_variant_public_id(self, obj):
        return obj.variant.public_id if obj.variant_id else None

    def get_variant_options(self, obj):
        if not obj.variant_id:
            return None
        rows = []
        for link in obj.variant.attribute_values.select_related("attribute_value__attribute").all():
            av = link.attribute_value
            rows.append({"attribute": av.attribute.name, "value": av.value})
        return rows


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_zone_public_id = serializers.CharField(source='shipping_zone.public_id', read_only=True, allow_null=True)
    shipping_method_public_id = serializers.CharField(source='shipping_method.public_id', read_only=True, allow_null=True)
    customer = serializers.SerializerMethodField()
    coupon_public_id = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'public_id', 'order_number', 'status', 'subtotal', 'shipping_cost', 'total',
            'coupon_code', 'coupon_public_id', 'discount_amount', 'pricing_snapshot',
            'shipping_zone_public_id', 'shipping_method_public_id',
            'shipping_name', 'shipping_address',
            'phone', 'email', 'district',
            'tracking_number',
            'courier_provider', 'courier_tracking_code', 'courier_status',
            'extra_data',
            'customer', 'created_at', 'updated_at', 'items',
        ]
        read_only_fields = ['public_id', 'order_number']

    def get_coupon_public_id(self, obj):
        c = getattr(obj, "coupon", None)
        return c.public_id if c else None

    def get_customer(self, obj):
        customer = getattr(obj, "customer", None)
        if not customer:
            return None
        return {
            "public_id": customer.public_id,
            "name": customer.name,
            "phone": customer.phone,
        }


class OrderCreateSerializer(serializers.Serializer):
    """Stateless checkout: shipping fields + line items from the request body."""
    shipping_zone = serializers.SlugRelatedField(
        slug_field='public_id',
        queryset=ShippingZone.objects.none(),
    )
    shipping_method = serializers.SlugRelatedField(
        slug_field='public_id',
        queryset=ShippingMethod.objects.none(),
        allow_null=True,
        required=False,
    )
    shipping_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    shipping_address = serializers.CharField()
    district = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    products = serializers.ListField(
        child=serializers.DictField(),
        min_length=1
    )
    max_quantity_per_item = 1000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        store = self.context.get("store")
        if not store:
            return
        self.fields["shipping_zone"].queryset = ShippingZone.objects.filter(store=store, is_active=True)
        self.fields["shipping_method"].queryset = ShippingMethod.objects.filter(store=store, is_active=True)

    def validate_shipping_name(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Required.')
        return value.strip()

    def validate_phone(self, value):
        raw = (value or '').strip()
        if not raw:
            raise serializers.ValidationError('Required.')
        digits = ''.join(c for c in raw if c.isdigit())
        if len(digits) != 11 or not digits.startswith('01'):
            raise serializers.ValidationError(
                'Phone must be 11 digits, start with 01, and contain only numbers.'
            )
        return digits

    def validate_shipping_address(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Required.')
        return value.strip()

    def validate_products(self, value):
        from engine.apps.products.models import Product
        from engine.apps.products.variant_utils import resolve_storefront_variant

        if not value:
            raise serializers.ValidationError('At least one product is required.')
        store = self.context.get("store")
        if not store:
            raise serializers.ValidationError("Store context is required.")
        for product in value:
            allowed_keys = {"public_id", "quantity", "variant_public_id"}
            unknown_keys = set(product.keys()) - allowed_keys
            if unknown_keys:
                raise serializers.ValidationError(
                    f"Unknown product fields are not allowed: {', '.join(sorted(unknown_keys))}."
                )
            if 'public_id' not in product or 'quantity' not in product:
                raise serializers.ValidationError('Each product must have public_id and quantity.')
            public_id = str(product.get("public_id", "")).strip()
            if not public_id.startswith("prd_"):
                raise serializers.ValidationError("Invalid product public_id.")
            quantity = product.get("quantity")
            if not isinstance(quantity, int):
                raise serializers.ValidationError("Quantity must be an integer.")
            if quantity <= 0:
                raise serializers.ValidationError("Quantity must be greater than zero.")
            if quantity > self.max_quantity_per_item:
                raise serializers.ValidationError(
                    f"Quantity cannot exceed {self.max_quantity_per_item} per item."
                )
            p_obj = (
                Product.objects.filter(
                    public_id=public_id,
                    store=store,
                    is_active=True,
                    status=Product.Status.ACTIVE,
                )
                .first()
            )
            if not p_obj:
                raise serializers.ValidationError(f"Product {public_id} not found or unavailable.")
            resolve_storefront_variant(
                product=p_obj,
                variant_public_id=product.get("variant_public_id"),
            )
        return value
