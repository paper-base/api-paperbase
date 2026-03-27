from __future__ import annotations

from dataclasses import dataclass

from engine.core.tenant_context import _tenant_context_exists, get_current_store
from engine.core.tenant_execution import in_tenant_scope


@dataclass(frozen=True)
class TenantSafeMigration:
    SYSTEM_SCOPE: str = "system"
    SINGLE_TENANT_SCOPE: str = "single_tenant"

    @classmethod
    def assert_write_scope(cls, *, scope: str) -> None:
        if scope not in {cls.SYSTEM_SCOPE, cls.SINGLE_TENANT_SCOPE}:
            raise RuntimeError(f"Unknown migration scope: {scope}")
        if scope == cls.SYSTEM_SCOPE:
            if in_tenant_scope() or get_current_store() is not None or _tenant_context_exists():
                raise RuntimeError("SYSTEM_SCOPE migrations must run with tenant context disabled.")
            return
        if get_current_store() is None:
            raise RuntimeError("SINGLE_TENANT_SCOPE migrations require explicit tenant context.")
