"""
Marketing event dispatcher.

Resolves the active store from explicit context, looks up enabled marketing
integrations, checks per-event toggles, and delegates to provider-specific
service modules. All exceptions are caught so callers are never broken.

Deterministic Meta ``event_id`` values are built in ``meta_event_ids`` (no random
UUID fallbacks). If an ID cannot be built (e.g. missing session), the event is
skipped and an error is logged.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.apps.marketing_integrations import meta_event_ids
from engine.core.tenant_guard import TenantViolationError

logger = logging.getLogger(__name__)

# Must match BooleanField defaults on IntegrationEventSettings — getattr(..., False) was wrong
# for flags that default to True: a missing attribute would skip sending Purchase / InitiateCheckout.
_EVENT_FLAG_DEFAULTS: dict[str, bool] = {
    "track_purchase": True,
    "track_initiate_checkout": True,
    "track_view_content": False,
    "track_search": False,
}


def _should_skip_event_for_settings(settings, event_flag: str) -> bool:
    """Skip only when integration has settings and the flag is explicitly off."""
    if not settings:
        return False
    default = _EVENT_FLAG_DEFAULTS.get(event_flag, True)
    enabled = bool(getattr(settings, event_flag, default))
    return not enabled


def _resolve_store_for_request(request):
    """
    Resolve store explicitly from the request.

    STRICT: no implicit ContextVar store resolution is allowed for Meta CAPI.
    """
    from rest_framework.exceptions import AuthenticationFailed

    from engine.core.tenancy import require_api_key_store

    try:
        return require_api_key_store(request)
    except AuthenticationFailed as exc:
        raise TenantViolationError("Dispatcher requires explicit store context.") from exc


def _meta_capi_allowed(store) -> bool:
    """
    Feature gate: key 'meta_capi', default ALLOW.

    - Missing key => allow
    - Explicit False => block
    """
    try:
        from engine.apps.billing import feature_gate
    except Exception:
        # Fail open: feature gating must never break tracking flow.
        return True

    owner = getattr(store, "owner", None)
    if owner is None:
        return True

    try:
        cfg = feature_gate.get_feature_config(owner) or {}
        features = cfg.get("features") if isinstance(cfg, dict) else {}
        if not isinstance(features, dict):
            return True
        if "meta_capi" not in features:
            return True
        return features.get("meta_capi") is not False
    except Exception:
        return True


def _get_integrations(store):
    """Fetch active marketing integrations with event settings for a store."""
    from engine.apps.marketing_integrations.models import MarketingIntegration

    return (
        MarketingIntegration.objects
        .filter(store=store, is_active=True)
        .select_related("event_settings")
    )


def _dispatch(request, event_flag: str, event_name: str, payload: dict[str, Any], *, store=None) -> None:
    """
    Core dispatch loop.

    Args:
        request: The incoming HTTP request.
        event_flag: Attribute name on IntegrationEventSettings (e.g. "track_purchase").
        event_name: Meta standard event name (e.g. "Purchase").
        payload: JSON-serializable payload including user_data/custom_data/metadata.
    """
    from engine.apps.marketing_integrations.tasks import send_capi_event

    if store is None:
        store = _resolve_store_for_request(request)
    if not store:
        raise TenantViolationError("Dispatcher requires explicit tenant context.")

    if not _meta_capi_allowed(store):
        return

    try:
        integrations = list(_get_integrations(store))
    except Exception:
        integrations = []
    if not integrations:
        return

    # Preserve existing per-event integration settings semantics: skip enqueue if
    # no active integration has the event enabled.
    any_enabled = False
    for integration in integrations:
        try:
            settings = getattr(integration, "event_settings", None)
            if _should_skip_event_for_settings(settings, event_flag):
                continue
            any_enabled = True
            break
        except Exception:
            continue
    if not any_enabled:
        return

    event_id = (payload or {}).get("event_id") or ""
    if not isinstance(event_id, str) or not event_id.strip():
        return

    try:
        send_capi_event.delay(
            store.public_id,
            event_name,
            event_id,
            payload or {},
        )
    except Exception:
        logger.exception("Failed to enqueue Meta CAPI event '%s'.", event_name)


def track_purchase(request, order) -> None:
    # Always pass the order's store: dashboard requests (esp. superusers) often have no
    # tenant in ContextVar (middleware clears it for platform scope), while storefront
    # InitiateCheckout still resolves via API key.
    try:
        eid = meta_event_ids.build_purchase_event_id(order)
    except ValueError as e:
        logger.error("Meta CAPI skip (purchase): %s", e)
        return
    store = getattr(order, "store", None)
    if store is None:
        raise TenantViolationError("Purchase tracking requires order.store.")
    from engine.apps.marketing_integrations.services import facebook_service

    payload = facebook_service.build_capi_payload_purchase(request=request, order=order, event_id=eid)
    _dispatch(request, "track_purchase", "Purchase", payload, store=store)


def track_initiate_checkout(request) -> None:
    eid = meta_event_ids.build_checkout_event_id(request)
    if not eid:
        logger.error(
            "Meta CAPI skip (initiate_checkout): no Django session key; cannot build deterministic event_id",
        )
        return
    from engine.apps.marketing_integrations.services import facebook_service

    store = _resolve_store_for_request(request)
    payload = facebook_service.build_capi_payload_initiate_checkout(request=request, event_id=eid)
    _dispatch(request, "track_initiate_checkout", "InitiateCheckout", payload, store=store)


def track_view_content(request, product) -> None:
    eid = meta_event_ids.build_view_content_event_id(product)
    if not eid:
        logger.error(
            "Meta CAPI skip (view_content): missing product.public_id",
        )
        return
    from engine.apps.marketing_integrations.services import facebook_service

    store = _resolve_store_for_request(request)
    payload = facebook_service.build_capi_payload_view_content(
        request=request,
        product=product,
        store=store,
        event_id=eid,
    )
    _dispatch(request, "track_view_content", "ViewContent", payload, store=store)


def track_search(request, query: str) -> None:
    eid = meta_event_ids.build_search_event_id(request, query)
    if not eid:
        logger.error(
            "Meta CAPI skip (search): no Django session key; cannot build deterministic event_id",
        )
        return
    from engine.apps.marketing_integrations.services import facebook_service

    store = _resolve_store_for_request(request)
    payload = facebook_service.build_capi_payload_search(request=request, query=query, event_id=eid)
    _dispatch(request, "track_search", "Search", payload, store=store)
