from django.db import models

from engine.apps.stores.models import Store

from .presets import DEFAULT_PALETTE, PALETTE_CHOICES


class StorefrontTheme(models.Model):
    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="theme",
    )
    palette = models.CharField(
        max_length=50,
        choices=[(k, k) for k in PALETTE_CHOICES],
        default=DEFAULT_PALETTE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Storefront Theme"

    def __str__(self) -> str:
        return f"Theme({self.store_id})"
