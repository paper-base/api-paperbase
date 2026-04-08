from __future__ import annotations

import os

from django.conf import settings

from engine.core.safety.tenant_safety import log_tenant_violation
from django.db import models

from engine.core.tenant_context import (
    TenantContextMissingError,
    _tenant_context_exists,
    get_current_store,
    get_is_platform_admin,
)
from engine.core.tenant_execution import in_system_scope


class TenantViolationError(RuntimeError):
    """Raised when an unsafe unscoped tenant query is attempted."""


class TenantIsolationError(TenantContextMissingError):
    """Raised when a tenant-isolated model is queried without store scope."""


def is_tenant_model(model: type[models.Model]) -> bool:
    """True if the model has a ForeignKey ``store`` to ``Store`` (tenant-owned row)."""
    try:
        field = model._meta.get_field("store")
    except Exception:
        return False
    rel = getattr(field, "related_model", None)
    return rel is not None and rel.__name__ == "Store"


def _is_production() -> bool:
    return not bool(getattr(settings, "DEBUG", False)) and not bool(
        getattr(settings, "TESTING", False)
    )


def strict_guard_enabled() -> bool:
    if _is_production():
        return True
    if bool(getattr(settings, "TENANT_GUARD_STRICT_DEV", False)):
        return True
    return os.getenv("CI", "").strip().lower() in {"1", "true", "yes", "on"}


def validate_tenant_query_allowed(*, model_name: str, operation: str) -> None:
    if in_system_scope():
        return
    store = get_current_store()
    if store is not None:
        return
    if get_is_platform_admin():
        return
    if strict_guard_enabled():
        log_tenant_violation(model_name=model_name, operation=operation)
        if _tenant_context_exists():
            raise TenantViolationError(
                f"Tenant context incomplete for {model_name}.{operation}."
            )
        raise TenantContextMissingError(
            f"Missing tenant context for {model_name}.{operation}."
        )
