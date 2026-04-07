"""Append-only audit rows for store lifecycle security events."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractUser

from .models import Store, StoreLifecycleAuditLog


def write_store_lifecycle_audit(
    *,
    user: AbstractUser | None,
    store: Store,
    action: StoreLifecycleAuditLog.Action | str,
    metadata: dict[str, Any] | None = None,
) -> None:
    StoreLifecycleAuditLog.objects.create(
        user=user,
        store=store,
        store_public_id=store.public_id,
        action=action,
        metadata=metadata or {},
    )
