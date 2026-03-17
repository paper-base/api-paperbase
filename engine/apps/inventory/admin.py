from django.contrib import admin
from .models import Inventory, StockMovement


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ['change', 'reason', 'reference', 'created_at', 'actor']


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'variant', 'quantity', 'low_stock_threshold', 'is_tracked', 'updated_at']
    list_filter = ['is_tracked']
    search_fields = ['product__name', 'variant__sku']
    readonly_fields = ['updated_at']
    inlines = [StockMovementInline]
    autocomplete_fields = ['product', 'variant']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['inventory', 'change', 'reason', 'reference', 'created_at', 'actor']
    list_filter = ['reason']
    readonly_fields = ['inventory', 'change', 'reason', 'reference', 'created_at', 'actor']
    date_hierarchy = 'created_at'
