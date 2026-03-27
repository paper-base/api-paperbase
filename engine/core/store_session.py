from __future__ import annotations

import hashlib
import hmac
import secrets
import logging
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from engine.apps.stores.models import StoreSession


STORE_SESSION_HEADER = "X-Store-Session-Token"
STORE_SESSION_COOKIE = "store_session_token"
STORE_SESSION_ID_RESPONSE_HEADER = "X-Store-Session-Id"
STORE_SESSION_TOKEN_RESPONSE_HEADER = "X-Store-Session-Token"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoreSessionContext:
    store: object | None
    store_session_token: str
    store_session_id: str
    session_initialized: bool


def _session_secret() -> bytes:
    secret = (getattr(settings, "SECRET_KEY", "") or "").encode("utf-8")
    if not secret:
        raise RuntimeError("SECRET_KEY is required for store session derivation.")
    return secret


def _extract_session_token(request) -> str:
    token = (request.headers.get(STORE_SESSION_HEADER) or "").strip()
    if token:
        return token
    cookie_token = (request.COOKIES.get(STORE_SESSION_COOKIE) or "").strip()
    return cookie_token


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def derive_store_session_id(*, store_id: int, token: str) -> str:
    message = f"{store_id}:{token}".encode("utf-8")
    digest = hmac.new(_session_secret(), message, hashlib.sha256).hexdigest()[:32]
    return f"ssn_{digest}"


def validate_store_session_consistency(*, store, token: str, store_session_id: str) -> bool:
    if not store or not token or not store_session_id:
        return False
    expected = derive_store_session_id(store_id=store.id, token=token)
    return hmac.compare_digest(expected, store_session_id)


def resolve_store_session(request) -> StoreSessionContext:
    store = getattr(request, "store", None)
    if not store:
        return StoreSessionContext(
            store=None,
            store_session_token="",
            store_session_id="",
            session_initialized=False,
        )

    token = _extract_session_token(request)
    session_initialized = bool(token)
    if not token:
        # Session creation is centralized here only.
        token = secrets.token_urlsafe(24)
        session_initialized = False
    store_session_id = derive_store_session_id(store_id=store.id, token=token)
    if not validate_store_session_consistency(
        store=store,
        token=token,
        store_session_id=store_session_id,
    ):
        raise RuntimeError("Store session consistency validation failed.")

    token_hash = _hash_token(token)
    session_row, _ = StoreSession.objects.get_or_create(
        store=store,
        token_hash=token_hash,
        defaults={"store_session_id": store_session_id},
    )
    # DB is a lifecycle projection, not an identity authority.
    if session_row.store_session_id != store_session_id:
        logger.warning(
            "StoreSession drift detected; derived identity remains authoritative. "
            "store_id=%s token_hash_prefix=%s persisted_id=%s derived_id=%s",
            store.id,
            token_hash[:12],
            session_row.store_session_id,
            store_session_id,
        )
        metrics_hook = getattr(settings, "STORE_SESSION_DRIFT_METRICS_HOOK", None)
        if callable(metrics_hook):
            metrics_hook()
    # Optional TTL hook: scaffold only, no hard expiry enforcement yet.
    _ = int(getattr(settings, "STORE_SESSION_TTL_SECONDS", "0") or 0)
    session_row.last_seen_at = timezone.now()
    session_row.save(update_fields=["last_seen_at"])

    context = StoreSessionContext(
        store=store,
        store_session_token=token,
        store_session_id=store_session_id,
        session_initialized=session_initialized,
    )
    attach_store_session_to_request(request, context)
    return context


def attach_store_session_to_request(request, context: StoreSessionContext) -> None:
    request.store_session_id = context.store_session_id
    request.store_session_token = context.store_session_token
    request.store_session_initialized = context.session_initialized
    # DRF wraps Django's HttpRequest; mirror session context onto the
    # underlying request so middleware process_response can emit headers.
    raw_request = getattr(request, "_request", None)
    if raw_request is not None:
        raw_request.store_session_id = context.store_session_id
        raw_request.store_session_token = context.store_session_token
        raw_request.store_session_initialized = context.session_initialized


def attach_store_session_to_response(request, response) -> None:
    store_session_id = getattr(request, "store_session_id", None)
    store_session_token = getattr(request, "store_session_token", None)
    if not store_session_id or not store_session_token:
        return
    response[STORE_SESSION_ID_RESPONSE_HEADER] = store_session_id
    response[STORE_SESSION_TOKEN_RESPONSE_HEADER] = store_session_token
    response.set_cookie(
        STORE_SESSION_COOKIE,
        store_session_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        max_age=60 * 60 * 24 * 30,
    )
