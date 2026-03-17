from decimal import Decimal

from django.conf import settings
from django.db import models


class PaymentMethod(models.Model):
    """Configured payment method (card, COD, bank transfer, external gateway)."""

    class MethodType(models.TextChoices):
        CARD = 'card', 'Card'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        COD = 'cod', 'Cash on delivery'
        EXTERNAL_GATEWAY = 'external_gateway', 'External gateway'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=100)
    method_type = models.CharField(max_length=30, choices=MethodType.choices, default=MethodType.OTHER)
    config = models.JSONField(default=dict, blank=True, help_text="Gateway-specific config (keys, webhook secret, etc.)")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Payment(models.Model):
    """Payment attempt for an order."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payments',
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    gateway_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} - {self.order.order_number} - {self.status}"


class Transaction(models.Model):
    """Granular gateway request/response for auditing."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    transaction_reference = models.CharField(max_length=255, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.transaction_reference or self.id} - {self.status}"
