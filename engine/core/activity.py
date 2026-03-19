from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser

from .models import ActivityLog


def log_activity(
    *,
    request,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    from engine.core.tenancy import get_active_store

    actor = getattr(request, "user", None)
    if isinstance(actor, AnonymousUser):
        actor = None

    try:
        ctx = get_active_store(request)
        store = ctx.store
    except Exception:
        store = None

    ActivityLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        store=store,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else "",
        summary=summary[:255],
        metadata=metadata or {},
    )

