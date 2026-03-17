import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from engine.apps.products.models import Product
from engine.apps.stores.models import Store


class OrderNumberCounter(models.Model):
    """Single-row table for atomic sequential order number generation."""
    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="order_counter",
    )
    next_value = models.PositiveBigIntegerField(default=1)


class Order(models.Model):
    """Order for checkout and track-order. Status lifecycle: Pending -> Confirmed -> Processing -> Shipped -> Delivered (or Cancelled/Returned)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        RETURNED = 'returned', 'Returned'

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        max_length=20, unique=True, db_index=True, editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )
    email = models.EmailField(blank=True, default='')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_name = models.CharField(max_length=255, blank=True)
    shipping_address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    delivery_area = models.CharField(max_length=50, blank=True, default='')
    district = models.CharField(max_length=100, blank=True, default='')
    tracking_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        display_id = self.order_number or str(self.id)[:8]
        return f"Order {display_id}"


class OrderAddress(models.Model):
    """Shipping or billing address snapshot for an order."""

    class AddressType(models.TextChoices):
        SHIPPING = 'shipping', 'Shipping'
        BILLING = 'billing', 'Billing'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=AddressType.choices)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100)

    class Meta:
        ordering = ['order', 'address_type']
        unique_together = [['order', 'address_type']]

    def __str__(self):
        return f"{self.order.order_number} - {self.get_address_type_display()}"


class OrderStatusHistory(models.Model):
    """Audit trail of order status changes."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Order status history'

    def __str__(self):
        return f"{self.order.order_number} -> {self.status}"


class OrderItem(models.Model):
    """Line item in an order with price snapshot."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='order_items',
    )
    quantity = models.PositiveIntegerField()
    size = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.order} - {self.product.name} x{self.quantity}"
