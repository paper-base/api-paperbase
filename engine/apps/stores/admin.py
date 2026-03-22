from django.contrib import admin

from .models import Domain, Store, StoreMembership, StoreSettings


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("public_id", "domain", "store", "is_custom", "is_verified", "is_primary", "created_at")
    list_filter = ("is_custom", "is_verified", "is_primary")
    search_fields = ("public_id", "domain", "store__name", "store__public_id")
    raw_id_fields = ("store",)
    ordering = ("-created_at",)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "domain", "owner_name", "owner_email", "currency_symbol", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "domain", "owner_name", "owner_email")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("name", "store_type", "domain", "is_active")}),
        ("Owner", {"fields": ("owner_name", "owner_email")}),
        ("Branding", {"fields": ("logo", "currency", "currency_symbol")}),
        ("Store info", {"fields": ("contact_email", "phone", "address")}),
    )


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ("store", "low_stock_threshold", "created_at")
    search_fields = ("store__name", "store__domain")


@admin.register(StoreMembership)
class StoreMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "store", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "created_at")
    search_fields = ("user__email", "store__name", "store__domain")
    raw_id_fields = ("user", "store")

