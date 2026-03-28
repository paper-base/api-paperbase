from django.conf import settings
from django.db import models

from engine.core.ids import generate_public_id
from engine.apps.products.models import Product


class WishlistItem(models.Model):
    """Wishlist entry for an authenticated user."""

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier (e.g. wsh_xxx).",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_wishlist_item",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} - {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("wishlist")
        super().save(*args, **kwargs)
