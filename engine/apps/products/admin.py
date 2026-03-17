from django.contrib import admin
from django.utils.html import mark_safe

from .models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttribute,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'sku',
        'brand',
        'get_category',
        'price',
        'stock',
        'status',
        'badge',
        'is_featured',
        'is_active',
    ]
    list_editable = ['stock', 'is_active']
    list_filter = ['category', 'status', 'badge', 'is_featured', 'is_active']
    search_fields = ['name', 'brand', 'sku']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    autocomplete_fields = ['category']
    fieldsets = (
        (None, {
            'fields': ('name', 'brand', 'slug', 'sku', 'status', 'category')
        }),
        ('Pricing', {
            'fields': ('price', 'original_price', 'badge')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Stock', {
            'fields': ('stock', 'stock_tracking')
        }),
        ('Additional Information', {
            'fields': ('description', 'is_featured', 'is_active')
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'stock' and field:
            field.widget.attrs.update({'style': 'width: 5rem;'})
        return field

    def get_category(self, obj):
        return obj.category.name if obj.category else '-'

    get_category.short_description = 'Category'
    get_category.admin_order_field = 'category__name'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'order', 'is_active', 'product_count']
    list_filter = ['parent', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['parent__name', 'order', 'name']
    readonly_fields = ['image_preview']
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent', 'description')
        }),
        ('Media', {
            'fields': ('image', 'image_preview'),
        }),
        ('Display', {
            'fields': ('order', 'is_active')
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" style="max-height:120px;" />')
        return '(no image uploaded)'

    image_preview.short_description = 'Current Image'

    def product_count(self, obj):
        count = obj.products.count()
        return f"{count} products"

    product_count.short_description = 'Products'


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand_type', 'order', 'is_active', 'redirect_url_preview', 'created_at']
    list_filter = ['brand_type', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['brand_type', 'order', 'name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'image')
        }),
        ('Configuration', {
            'fields': ('brand_type', 'redirect_url', 'order', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def redirect_url_preview(self, obj):
        url = obj.redirect_url
        if len(url) > 40:
            return f"{url[:40]}..."
        return url

    redirect_url_preview.short_description = 'Redirect URL'


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 0
    ordering = ['order']


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    list_editable = ['order']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductAttributeValueInline]


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ['value', 'attribute', 'order']
    list_filter = ['attribute']
    list_editable = ['order']
    ordering = ['attribute', 'order']
    search_fields = ['value', 'attribute__name']


class ProductVariantAttributeInline(admin.TabularInline):
    model = ProductVariantAttribute
    extra = 0
    autocomplete_fields = ['attribute_value']


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'sku', 'price_override', 'stock_quantity', 'is_active', 'created_at']
    list_filter = ['is_active']
    list_editable = ['stock_quantity', 'is_active']
    search_fields = ['sku', 'product__name']
    inlines = [ProductVariantAttributeInline]
    autocomplete_fields = ['product']
