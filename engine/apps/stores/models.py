from django.conf import settings
from django.db import models


class Store(models.Model):
    """Tenant store for the BaaS platform."""

    name = models.CharField(max_length=255)
    domain = models.CharField(
        max_length=255,
        unique=True,
        help_text="Full domain or host used to route requests to this store.",
    )
    is_active = models.BooleanField(default=True)
    timezone = models.CharField(max_length=64, default="UTC")
    currency = models.CharField(max_length=8, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["is_active", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.domain})"


class StoreSettings(models.Model):
    """Per-store configuration and feature flags."""

    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    modules_enabled = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature/module flags for this store (e.g. products, orders, reviews).",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Default low-stock alert threshold for inventory.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Store settings"

    def __str__(self) -> str:
        return f"Settings for {self.store}"


class StoreMembership(models.Model):
    """Association between a user and a store, with a role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_memberships",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "store"],
                name="uniq_store_membership_user_store",
            ),
        ]
        indexes = [
            models.Index(fields=["store", "role"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.store} ({self.get_role_display()})"

