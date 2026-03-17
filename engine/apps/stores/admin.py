from django.contrib import admin

from .models import Store, StoreSettings, StoreMembership


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "domain", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "domain")
    ordering = ("-created_at",)


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ("store", "low_stock_threshold", "created_at")
    search_fields = ("store__name", "store__domain")


@admin.register(StoreMembership)
class StoreMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "store", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("user__username", "user__email", "store__name", "store__domain")
    autocomplete_fields = ("user", "store")

