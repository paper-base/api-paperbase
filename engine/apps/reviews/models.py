from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

from engine.core.ids import generate_public_id
from engine.apps.stores.models import Store
from engine.core.tenant_queryset import TenantAwareManager


class Review(models.Model):
    """Product review with star rating and optional moderation."""

    public_id = models.CharField(
        max_length=32, unique=True, db_index=True, editable=False,
        help_text="Non-sequential public identifier (e.g. rev_xxx).",
    )

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="reviews",
        db_index=True,
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_reviews',
    )
    allow_legacy_binding = models.BooleanField(
        default=False,
        help_text="Internal override to allow legacy/support review binding exceptions.",
    )
    rating = models.PositiveSmallIntegerField(
        help_text="1-5 stars",
    )
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    objects = TenantAwareManager()

    def clean(self):
        if not self.order_id:
            raise ValidationError({"order": "Review must reference an order."})
        if self.store_id != self.product.store_id:
            raise ValidationError({"store": "Review store must match product store."})
        if self.store_id != self.order.store_id:
            raise ValidationError({"store": "Review store must match order store."})
        if self.product.store_id != self.order.store_id:
            raise ValidationError({"order": "Review order and product must belong to the same store."})
        from engine.apps.orders.models import OrderItem
        if not OrderItem.objects.filter(order=self.order, product=self.product).exists():
            raise ValidationError({"order": "Review order must include the reviewed product."})

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("review")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Review {self.product.name} by {self.user_id} - {self.rating}"
