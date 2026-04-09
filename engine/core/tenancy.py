from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from django.http import HttpRequest

from engine.apps.stores.models import Store, StoreMembership
from engine.core.tenant_context import _set_tenant_context


def _is_platform_scope_user(request: HttpRequest) -> bool:
    from engine.core.request_context import user_enters_platform_scope

    user = getattr(request, "user", None)
    return bool(user_enters_platform_scope(user))

logger = logging.getLogger(__name__)


class ActiveStoreProvenance(str, Enum):
    """How the active store was resolved; used to validate proof of access."""

    NONE = "none"
    API_KEY = "api_key"
    SUPERUSER_HEADER = "superuser_header"
    OWNER_STORE = "owner_store"
    MEMBERSHIP_HEADER = "membership_header"
    MEMBERSHIP_JWT = "membership_jwt"


@dataclass
class ActiveStoreContext:
    store: Optional[Store]
    membership: Optional[StoreMembership]
    provenance: ActiveStoreProvenance = ActiveStoreProvenance.NONE


class InvalidTenantContextError(Exception):
    """Raised when a store is implied but cannot be validated against the auth source."""


def assert_instance_belongs_to_store(instance, store: Store) -> None:
    """
    For create/update/destroy: ensure the target instance is scoped to the active store.
    """
    from rest_framework.exceptions import PermissionDenied

    sid = getattr(instance, "store_id", None)
    if sid is None and getattr(instance, "store", None) is not None:
        sid = getattr(instance.store, "pk", None)
    if store is None or sid is None or int(sid) != int(store.pk):
        raise PermissionDenied(detail="Object does not belong to the active store.")


def _membership_for(user, store: Store) -> Optional[StoreMembership]:
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return StoreMembership.objects.get(
            user=user,
            store=store,
            is_active=True,
        )
    except StoreMembership.DoesNotExist:
        return None


def _read_active_store_public_id_from_auth(request: HttpRequest) -> str | None:
    auth = getattr(request, "auth", None)
    if auth is None:
        return None
    token_store_public_id = None
    if hasattr(auth, "get"):
        try:
            token_store_public_id = auth.get("active_store_public_id")  # type: ignore[union-attr]
        except Exception:
            token_store_public_id = None
    if token_store_public_id is None:
        try:
            token_store_public_id = auth["active_store_public_id"]  # type: ignore[index]
        except Exception:
            token_store_public_id = None
    return token_store_public_id


def get_active_store(request: HttpRequest) -> ActiveStoreContext:
    """
    Resolve the active store for the current request.

    Priority:
    1) API key-resolved request.store (storefront / tenant public APIs)
    2) Superuser: optional X-Store-Public-ID for platform tooling
    3) Authenticated store owner: request.user.owned_store (ignores client store hints)
    4) Authenticated non-owner with membership: header store hint (X-Store-Public-ID)
    5) Authenticated non-owner: JWT claim active_store_public_id (membership validated)

    Anonymous X-Store-Public-ID alone does not resolve a store; tenant ContextVar is
    bound after DRF authentication via ProvenTenantContextMixin.
    """
    store_from_api_key = getattr(request, "store", None)
    store: Optional[Store] = store_from_api_key
    membership: Optional[StoreMembership] = None
    provenance = ActiveStoreProvenance.NONE
    user = getattr(request, "user", None)

    # 1) Storefront API key
    if store is not None:
        provenance = ActiveStoreProvenance.API_KEY
        if user and getattr(user, "is_authenticated", False):
            membership = _membership_for(user, store)
        return ActiveStoreContext(store=store, membership=membership, provenance=provenance)

    # 2) Platform superuser
    if getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False):
        header_store_public_id = request.headers.get("X-Store-Public-ID") or request.headers.get(
            "x-store-public-id"
        )
        if header_store_public_id:
            store = Store.objects.filter(public_id=header_store_public_id).first()
        if store:
            membership = _membership_for(user, store)
            provenance = ActiveStoreProvenance.SUPERUSER_HEADER
        return ActiveStoreContext(store=store, membership=membership, provenance=provenance)

    # 3) Owner: single source of truth — never trust header/JWT for tenancy
    if getattr(user, "is_authenticated", False):
        owned = getattr(user, "owned_store", None)
        if owned is not None:
            store = owned
            membership = _membership_for(user, store)
            return ActiveStoreContext(
                store=store,
                membership=membership,
                provenance=ActiveStoreProvenance.OWNER_STORE,
            )

    # 4) Authenticated non-owner: explicit store selection via header (membership validated).
    if getattr(user, "is_authenticated", False):
        header_store_public_id = request.headers.get("X-Store-Public-ID")
        if header_store_public_id:
            candidate = Store.objects.filter(public_id=header_store_public_id).first()
            if candidate:
                membership = _membership_for(user, candidate)
                if membership is not None:
                    return ActiveStoreContext(
                        store=candidate,
                        membership=membership,
                        provenance=ActiveStoreProvenance.MEMBERSHIP_HEADER,
                    )

    # 5) Authenticated non-owner: JWT claim (membership validated before accepting)
    if getattr(user, "is_authenticated", False) and getattr(request, "auth", None):
        token_store_public_id = _read_active_store_public_id_from_auth(request)
        store_jwt: Optional[Store] = None
        membership_jwt: Optional[StoreMembership] = None
        if token_store_public_id:
            store_jwt = Store.objects.filter(public_id=token_store_public_id).first()
        if store_jwt:
            membership_jwt = _membership_for(user, store_jwt)
        if membership_jwt is None:
            store_jwt = None
        return ActiveStoreContext(
            store=store_jwt,
            membership=membership_jwt,
            provenance=ActiveStoreProvenance.MEMBERSHIP_JWT,
        )

    return ActiveStoreContext(store=None, membership=None, provenance=ActiveStoreProvenance.NONE)


def store_proof_ok(ctx: ActiveStoreContext, request: HttpRequest) -> bool:
    """Return True if ctx.store is backed by a valid auth source for this request."""
    if ctx.store is None:
        return True
    user = getattr(request, "user", None)
    api_key = getattr(request, "api_key", None)
    req_store = getattr(request, "store", None)

    if ctx.provenance == ActiveStoreProvenance.API_KEY:
        return bool(
            api_key
            and req_store is not None
            and getattr(req_store, "pk", None) == getattr(ctx.store, "pk", None)
        )

    if ctx.provenance == ActiveStoreProvenance.SUPERUSER_HEADER:
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_superuser", False)
        )

    if ctx.provenance == ActiveStoreProvenance.OWNER_STORE:
        owned = getattr(user, "owned_store", None) if user else None
        return bool(
            owned is not None and getattr(owned, "pk", None) == getattr(ctx.store, "pk", None)
        )

    if ctx.provenance in (
        ActiveStoreProvenance.MEMBERSHIP_HEADER,
        ActiveStoreProvenance.MEMBERSHIP_JWT,
    ):
        m = ctx.membership
        return bool(
            m is not None
            and getattr(m, "store_id", None) == getattr(ctx.store, "pk", None)
        )

    return False


def log_store_resolution(request: HttpRequest, ctx: ActiveStoreContext) -> None:
    """Structured log when a store is resolved (no secrets)."""
    if ctx.store is None:
        return
    user = getattr(request, "user", None)
    uid = getattr(user, "public_id", None) if user else None
    logger.debug(
        "tenant.store_resolved",
        extra={
            "provenance": ctx.provenance.value,
            "store_public_id": getattr(ctx.store, "public_id", None),
            "user_public_id": uid,
        },
    )


def require_valid_store_context(request: HttpRequest) -> tuple[Store, ActiveStoreProvenance]:
    """
    Return the active store only if resolution is backed by a valid auth source.

    Use for dashboard and other tenant endpoints after DRF authentication.
    """
    from rest_framework.exceptions import NotFound, PermissionDenied

    ctx = get_active_store(request)
    if ctx.store is None:
        raise NotFound(detail="No active store for this request.")

    if not store_proof_ok(ctx, request):
        logger.warning(
            "tenant.store_context_invalid_proof",
            extra={
                "provenance": ctx.provenance.value,
                "store_public_id": getattr(ctx.store, "public_id", None),
            },
        )
        raise PermissionDenied(detail="Store context could not be validated for this request.")

    if ctx.provenance == ActiveStoreProvenance.SUPERUSER_HEADER:
        logger.info(
            "tenant.superuser_store_override",
            extra={
                "store_public_id": getattr(ctx.store, "public_id", None),
                "user_public_id": getattr(request.user, "public_id", None),
            },
        )

    log_store_resolution(request, ctx)
    return ctx.store, ctx.provenance


def require_resolved_store(request: HttpRequest) -> None:
    """
    DRF storefront views: require API-key resolved store context.
    """
    from rest_framework.exceptions import AuthenticationFailed

    if getattr(request, "store", None) is None:
        raise AuthenticationFailed(detail="Store context missing.")


def require_api_key_store(request: HttpRequest) -> Store:
    """
    Return request.store for storefront flows; fail closed if absent.
    """
    from rest_framework.exceptions import AuthenticationFailed

    store = getattr(request, "store", None)
    if store is None:
        raise AuthenticationFailed(detail="Store context missing.")
    return store


def bind_validated_tenant_context(request: HttpRequest) -> None:
    """
    After DRF authentication, mirror proven tenant resolution to ContextVar and request.context.

    No-op when no store is resolved. Raises PermissionDenied if a store is implied but proof fails.
    """
    from rest_framework.exceptions import PermissionDenied

    from engine.core.request_context import RequestContext

    ctx = get_active_store(request)
    if ctx.store is None:
        is_platform = _is_platform_scope_user(request)
        _set_tenant_context(store=None, is_platform_admin=is_platform)
        request.context = RequestContext(tenant=None, is_platform_admin=is_platform)
        return

    if not store_proof_ok(ctx, request):
        logger.warning(
            "tenant.bind_invalid_proof",
            extra={
                "provenance": ctx.provenance.value,
                "store_public_id": getattr(ctx.store, "public_id", None),
            },
        )
        raise PermissionDenied(detail="Store context could not be validated for this request.")

    # Admin API: reject X-Store-Public-ID that does not match the resolved active store
    # (JWT / membership), so clients cannot probe other tenants via header while
    # authenticated as another store. Non-admin routes (e.g. /api/v1/customers/) rely on
    # resolution order: JWT wins over a mismatched header without a 403.
    user = getattr(request, "user", None)
    if (
        user
        and getattr(user, "is_authenticated", False)
        and not getattr(user, "is_superuser", False)
    ):
        path = (request.path or "").strip()
        if path.startswith("/api/v1/admin/"):
            hdr = (
                request.headers.get("X-Store-Public-ID")
                or request.headers.get("x-store-public-id")
                or ""
            ).strip()
            if hdr and hdr != ctx.store.public_id:
                raise PermissionDenied(
                    detail="X-Store-Public-ID does not match the authenticated active store.",
                )

    if ctx.provenance == ActiveStoreProvenance.SUPERUSER_HEADER:
        logger.info(
            "tenant.superuser_store_override",
            extra={
                "store_public_id": getattr(ctx.store, "public_id", None),
                "user_public_id": getattr(request.user, "public_id", None),
            },
        )

    log_store_resolution(request, ctx)
    _set_tenant_context(store=ctx.store, is_platform_admin=False)
    request.context = RequestContext(tenant=ctx.store, is_platform_admin=False)
