from __future__ import annotations

from django.db import models

from engine.apps.stores.models import Store
from engine.core.tenant_queryset import TenantAwareManager


class FraudCheckLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="fraud_check_logs",
    )
    phone_number = models.CharField(max_length=32, db_index=True)
    normalized_phone = models.CharField(max_length=16, db_index=True)
    response_json = models.JSONField(blank=True, default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantAwareManager()

    class Meta:
        indexes = [
            models.Index(fields=["store", "normalized_phone"]),
        ]
        ordering = ["-checked_at", "-id"]

    def __str__(self) -> str:
        return f"{self.store.public_id} {self.normalized_phone} {self.status}"

