"""Append-only audit rows for store lifecycle security events."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractUser

from .models import Store, StoreLifecycleAuditLog


def write_store_lifecycle_audit(
    *,
    user: AbstractUser | None,
    store: Store | None,
    store_public_id: str | None = None,
    action: StoreLifecycleAuditLog.Action | str,
    metadata: dict[str, Any] | None = None,
) -> None:
    pid = (store_public_id or (store.public_id if store else "") or "").strip()
    if not pid:
        raise ValueError("store_public_id is required when store is None.")
    StoreLifecycleAuditLog.objects.create(
        user=user,
        store=store,
        store_public_id=pid,
        action=action,
        metadata=metadata or {},
    )
