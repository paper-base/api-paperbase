from rest_framework import serializers

from engine.apps.products.models import Product
from engine.core.tenancy import get_active_store

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    product_public_id = serializers.CharField(source='product.public_id', read_only=True)
    user_public_id = serializers.CharField(source='user.public_id', read_only=True)

    class Meta:
        model = Review
        fields = ['public_id', 'product_public_id', 'user_public_id', 'rating', 'title', 'body', 'created_at']
        read_only_fields = ['public_id', 'product_public_id', 'user_public_id']


class ReviewCreateSerializer(serializers.ModelSerializer):
    product = serializers.SlugRelatedField(
        slug_field='public_id',
        queryset=Product.objects.none(),
    )
    body = serializers.CharField(min_length=5, max_length=2000, allow_blank=False)
    order_public_id = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    allow_legacy_binding = serializers.BooleanField(write_only=True, required=False, default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        ctx = get_active_store(request) if request else None
        if ctx and ctx.store:
            self.fields["product"].queryset = Product.objects.filter(
                is_active=True,
                status=Product.Status.ACTIVE,
                store=ctx.store,
            )
        else:
            self.fields["product"].queryset = Product.objects.none()

    class Meta:
        model = Review
        fields = [
            'product',
            'rating',
            'title',
            'body',
            'order_public_id',
            'phone',
            'email',
            'allow_legacy_binding',
        ]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value

    def validate_product(self, value):
        public_id = getattr(value, "public_id", "") or ""
        if not str(public_id).startswith("prd_"):
            raise serializers.ValidationError("Invalid product_id format.")
        return value
