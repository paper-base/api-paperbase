from __future__ import annotations

import logging

from engine.core.tenant_context import (
    TenantContextMissingError,
    get_current_store,
    get_is_platform_admin,
)
from engine.core.tenant_execution import get_execution_scope, in_system_scope

logger = logging.getLogger(__name__)
_hooks_registered = False


def log_tenant_violation(*, model_name: str, operation: str) -> None:
    scope = get_execution_scope()
    logger.error(
        "Tenant safety violation: model=%s operation=%s scope=%s reason=%s",
        model_name,
        operation,
        scope.kind,
        scope.reason,
    )


def assert_tenant_scope_or_system(*, operation: str) -> None:
    if in_system_scope():
        return
    if get_is_platform_admin():
        return
    if get_current_store() is None:
        raise TenantContextMissingError(
            f"Tenant context missing for operation '{operation}'."
        )


def register_tenant_safety_hooks() -> None:
    global _hooks_registered
    if _hooks_registered:
        return
    _hooks_registered = True
