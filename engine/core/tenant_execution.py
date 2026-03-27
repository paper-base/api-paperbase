from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

from engine.core.tenant_context import (
    _reset_tenant_context,
    _set_tenant_context,
    require_store_context,
)

if TYPE_CHECKING:
    from engine.apps.stores.models import Store

SYSTEM_TENANT_ID = "__system__"


@dataclass(frozen=True)
class ExecutionScope:
    kind: str
    reason: str


_execution_scope: ContextVar[ExecutionScope] = ContextVar(
    "execution_scope",
    default=ExecutionScope(kind="none", reason=""),
)


def _set_execution_scope(*, kind: str, reason: str) -> Token:
    return _execution_scope.set(ExecutionScope(kind=kind, reason=reason))


def _reset_execution_scope(token: Token) -> None:
    _execution_scope.reset(token)


def get_execution_scope() -> ExecutionScope:
    return _execution_scope.get()


def in_system_scope() -> bool:
    return get_execution_scope().kind == "system"


def in_tenant_scope() -> bool:
    return get_execution_scope().kind == "tenant"


@contextmanager
def tenant_scope(*, store_id: int, session_id: str | None = None, reason: str = "") -> Iterator["Store"]:
    from engine.apps.stores.models import Store

    store = Store.objects.filter(id=store_id, is_active=True).first()
    if store is None:
        raise RuntimeError(f"Store {store_id} does not exist or is inactive.")
    scope_token = _set_execution_scope(kind="tenant", reason=reason or f"tenant:{store_id}")
    context_token = _set_tenant_context(store=store, session_id=session_id)
    try:
        yield store
    finally:
        _reset_tenant_context(context_token)
        _reset_execution_scope(scope_token)


@contextmanager
def tenant_scope_from_store(*, store: "Store", session_id: str | None = None, reason: str = "") -> Iterator["Store"]:
    scope_token = _set_execution_scope(kind="tenant", reason=reason or f"tenant:{store.id}")
    context_token = _set_tenant_context(store=store, session_id=session_id)
    try:
        yield store
    finally:
        _reset_tenant_context(context_token)
        _reset_execution_scope(scope_token)


@contextmanager
def system_scope(*, reason: str) -> Iterator[None]:
    if not reason.strip():
        raise RuntimeError("SYSTEM scope requires an explicit reason.")
    scope_token = _set_execution_scope(kind="system", reason=reason.strip())
    context_token = _set_tenant_context(store=None, session_id=None)
    try:
        yield None
    finally:
        _reset_tenant_context(context_token)
        _reset_execution_scope(scope_token)


def require_tenant_scope_store() -> Store:
    return require_store_context()
