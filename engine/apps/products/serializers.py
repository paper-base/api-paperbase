from rest_framework import serializers

from .models import Brand, Category, Product, ProductImage


def _image_url(img, request):
    if not img:
        return None
    return request.build_absolute_uri(img.url) if request else img.url


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'url', 'order']

    def get_url(self, obj):
        return _image_url(obj.image, self.context.get('request'))


class ProductListSerializer(serializers.ModelSerializer):
    """For list views: matches frontend Product shape."""
    id = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()
    originalPrice = serializers.DecimalField(
        source='original_price', max_digits=10, decimal_places=2,
        read_only=True, allow_null=True
    )
    # Return category slug for frontend URL generation
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'brand', 'price', 'originalPrice', 'image',
            'badge', 'category', 'slug', 'stock',
        ]

    def get_image(self, obj):
        return _image_url(obj.image, self.context.get('request'))


class ProductDetailSerializer(serializers.ModelSerializer):
    """For detail view: adds images, description, sub_category."""
    id = serializers.CharField(read_only=True)
    image = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    originalPrice = serializers.DecimalField(
        source='original_price', max_digits=10, decimal_places=2,
        read_only=True, allow_null=True
    )
    # Return category slug for frontend compatibility
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'brand', 'slug', 'price', 'originalPrice', 'image', 'images',
            'badge', 'category', 'description',
            'is_featured', 'created_at', 'stock',
        ]

    def get_image(self, obj):
        return _image_url(obj.image, self.context.get('request'))

    def get_images(self, obj):
        qs = obj.images.all()
        req = self.context.get('request')
        return [_image_url(i.image, req) for i in qs] if qs.exists() else []

class CategorySerializer(serializers.ModelSerializer):
    """Serializer for category tree nodes."""
    image = serializers.SerializerMethodField()
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        read_only=True,
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'parent_id', 'order']

    def get_image(self, obj):
        return _image_url(obj.image, self.context.get('request'))

    # Reuse same helper for category image path

class BrandSerializer(serializers.ModelSerializer):
    """Serializer for Brand model used in homepage brand showcase."""
    image = serializers.SerializerMethodField()
    redirectUrl = serializers.URLField(source='redirect_url', read_only=True)
    brandType = serializers.CharField(source='brand_type', read_only=True)

    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug', 'image', 'redirectUrl', 'brandType', 'order']

    def get_image(self, obj):
        return _image_url(obj.image, self.context.get('request'))
