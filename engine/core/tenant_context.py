from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


class TenantContextMissingError(RuntimeError):
    """Raised when tenant context is required but missing."""


@dataclass(frozen=True)
class _TenantContextState:
    store: object | None
    session_id: str | None


_tenant_context_state: ContextVar[_TenantContextState] = ContextVar(
    "tenant_context_state",
    default=_TenantContextState(store=None, session_id=None),
)
_tenant_context_default_state = _TenantContextState(store=None, session_id=None)


def _set_tenant_context(*, store: object | None, session_id: str | None) -> Token:
    clean_session = (session_id or "").strip() or None
    return _tenant_context_state.set(_TenantContextState(store=store, session_id=clean_session))


def _reset_tenant_context(token: Token) -> None:
    _tenant_context_state.reset(token)


def _clear_tenant_context() -> None:
    _tenant_context_state.set(_tenant_context_default_state)


def _tenant_context_exists() -> bool:
    state = _tenant_context_state.get()
    return bool(state.store is not None or (state.session_id or "").strip())


def get_current_store():
    return _tenant_context_state.get().store


def get_current_store_id() -> int:
    store = require_store_context()
    store_id = getattr(store, "id", None)
    if store_id is None:
        raise TenantContextMissingError("Current tenant store has no id.")
    return int(store_id)


def get_current_session_id() -> str:
    session_id = (_tenant_context_state.get().session_id or "").strip()
    if not session_id:
        raise TenantContextMissingError("Store session context is missing.")
    return session_id


def require_store_context():
    store = get_current_store()
    if store is None:
        raise TenantContextMissingError("Store context is missing.")
    return store
