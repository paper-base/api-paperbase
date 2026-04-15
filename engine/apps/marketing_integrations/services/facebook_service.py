"""
Facebook Conversions API integration service.

Sends server-side events to the Meta Marketing API.
Decryption of stored credentials happens exclusively inside this module.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import requests
from django.core.cache import cache

from engine.apps.marketing_integrations.meta_event_ids import meta_event_id_valid
from engine.core.encryption import decrypt_value

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v18.0"
GRAPH_API_BASE = "https://graph.facebook.com"


def _hash_value(value: str) -> str:
    """SHA-256 hash a value for Facebook user_data fields."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _extract_user_data(request) -> dict[str, Any]:
    """Build hashed user_data dict from the incoming request."""
    user_data: dict[str, Any] = {}

    ip = (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )
    if ip:
        user_data["client_ip_address"] = ip

    ua = request.META.get("HTTP_USER_AGENT", "")
    if ua:
        user_data["client_user_agent"] = ua

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        email = getattr(user, "email", "") or ""
        if email:
            user_data["em"] = [_hash_value(email)]
        external_id = getattr(user, "public_id", "") or ""
        if external_id:
            user_data["external_id"] = [_hash_value(external_id)]

    return user_data


def extract_user_data(request) -> dict[str, Any]:
    """Public wrapper: build hashed user_data from request metadata."""
    return _extract_user_data(request)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _currency_for(store, *, fallback: str = "USD") -> str:
    cur = (getattr(store, "currency", None) or "").strip()
    return cur or fallback


def build_purchase_custom_data(order) -> dict[str, Any]:
    currency = None
    try:
        currency = (getattr(order, "currency", None) or "").strip() or None
    except Exception:
        currency = None
    if not currency:
        currency = _currency_for(getattr(order, "store", None))

    total_value = _safe_float(getattr(order, "total", None))

    event_data: dict[str, Any] = {
        "currency": currency,
        "content_type": "product",
        "order_id": getattr(order, "public_id", "") or "",
    }
    if total_value is not None:
        event_data["value"] = total_value

    items = []
    try:
        items = list(order.items.select_related("product").all())
    except Exception:
        items = []
    if items:
        contents = []
        num_items = 0
        for item in items:
            product = getattr(item, "product", None)
            if not product:
                continue
            contents.append(
                {"id": getattr(product, "public_id", "") or "", "quantity": getattr(item, "quantity", 0)}
            )
            try:
                num_items += int(getattr(item, "quantity", 0) or 0)
            except Exception:
                pass
        if contents:
            event_data["contents"] = contents
        if num_items:
            event_data["num_items"] = num_items
    return event_data


def build_view_content_custom_data(product, *, store=None) -> dict[str, Any]:
    currency = None
    try:
        currency = (getattr(product, "currency", None) or "").strip() or None
    except Exception:
        currency = None
    if not currency:
        pstore = getattr(product, "store", None)
        currency = _currency_for(pstore or store)

    price = _safe_float(getattr(product, "price", None))
    event_data: dict[str, Any] = {
        "currency": currency,
        "content_type": "product",
        "contents": [{"id": getattr(product, "public_id", "") or "", "quantity": 1}],
        "content_name": getattr(product, "name", "") or "",
    }
    if price is not None:
        event_data["value"] = price
    return event_data


def build_capi_payload_purchase(*, request, order, event_id: str) -> dict[str, Any]:
    user_data = _extract_user_data(request)
    email = getattr(order, "email", "") or ""
    if email:
        user_data["em"] = [_hash_value(email)]
    phone = getattr(order, "phone", "") or ""
    if phone:
        user_data["ph"] = [_hash_value(phone)]
    custom_data = build_purchase_custom_data(order)
    metadata = {
        "order_public_id": getattr(order, "public_id", "") or "",
        "value": custom_data.get("value"),
        "currency": custom_data.get("currency"),
    }
    return {"event_id": event_id, "user_data": user_data, "custom_data": custom_data, "metadata": metadata}


def build_capi_payload_initiate_checkout(*, request, event_id: str) -> dict[str, Any]:
    user_data = _extract_user_data(request)
    return {"event_id": event_id, "user_data": user_data, "custom_data": {}, "metadata": {}}


def build_capi_payload_view_content(*, request, product, store, event_id: str) -> dict[str, Any]:
    user_data = _extract_user_data(request)
    custom_data = build_view_content_custom_data(product, store=store)
    metadata = {
        "product_public_id": getattr(product, "public_id", "") or "",
        "value": custom_data.get("value"),
        "currency": custom_data.get("currency"),
    }
    return {"event_id": event_id, "user_data": user_data, "custom_data": custom_data, "metadata": metadata}


def build_capi_payload_search(*, request, query: str, event_id: str) -> dict[str, Any]:
    user_data = _extract_user_data(request)
    return {"event_id": event_id, "user_data": user_data, "custom_data": {"search_string": query}, "metadata": {}}


def _should_db_log(event_name: str, status: str) -> bool:
    if status in {"failed", "skipped"}:
        return True
    return event_name in {"Purchase", "InitiateCheckout"}


def _try_log_store_event(
    *,
    store_public_id: str,
    event_name: str,
    status: str,
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        from engine.apps.marketing_integrations.models import StoreEventLog
        from engine.apps.stores.models import Store

        store = Store.objects.filter(public_id=store_public_id).first()
        if not store:
            return
        StoreEventLog.objects.create(
            store=store,
            app="marketing",
            event_type=f"capi_{(event_name or '').strip().lower()}",
            status=status,
            message=(message or "").strip()[:500] if message else "",
            metadata=metadata or {},
        )
    except Exception:
        # DB logging must never break the flow.
        return


def _send_event(
    integration,
    event_name: str,
    event_data: dict[str, Any],
    user_data: dict[str, Any],
    *,
    event_id: str,
    store_public_id: str,
    raise_on_error: bool = False,
) -> None:
    """Post a single event to the Facebook Conversions API."""
    if not event_id or not isinstance(event_id, str) or not event_id.strip():
        logger.error(
            "Meta CAPI skip: missing event_id for event_name=%s integration=%s",
            event_name,
            getattr(integration, "public_id", "—"),
        )
        return
    eid = event_id.strip()
    if not meta_event_id_valid(event_name, eid):
        logger.error(
            "Meta CAPI skip: invalid event_id format event_name=%s event_id=%r integration=%s",
            event_name,
            eid,
            getattr(integration, "public_id", "—"),
        )
        if _should_db_log(event_name, "failed"):
            _try_log_store_event(
                store_public_id=store_public_id,
                event_name=event_name,
                status="failed",
                message="invalid_event_id",
                metadata={"event_id": eid},
            )
        return

    access_token = decrypt_value(integration.access_token_encrypted)
    if not access_token or not integration.pixel_id:
        logger.warning("Facebook integration %s missing credentials, skipping.", integration.public_id)
        if _should_db_log(event_name, "failed"):
            _try_log_store_event(
                store_public_id=store_public_id,
                event_name=event_name,
                status="failed",
                message="missing_credentials",
                metadata={"event_id": eid, "pixel_id": getattr(integration, "pixel_id", "") or ""},
            )
        return

    url = f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{integration.pixel_id}/events"

    dedup_key = f"capi:{store_public_id}:{eid}"
    try:
        if cache.get(dedup_key) is not None:
            if _should_db_log(event_name, "skipped"):
                _try_log_store_event(
                    store_public_id=store_public_id,
                    event_name=event_name,
                    status="skipped",
                    message="dedup_skip",
                    metadata={"event_id": eid},
                )
            return
    except Exception:
        # Cache failures must not block sends.
        pass

    event_payload: dict[str, Any] = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": eid,
        "action_source": "website",
        "user_data": user_data,
    }
    if event_data:
        event_payload["custom_data"] = event_data

    body: dict[str, Any] = {
        "data": [event_payload],
        "access_token": access_token,
    }

    test_code = (integration.test_event_code or "").strip()
    if test_code:
        body["test_event_code"] = test_code

    try:
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to send Facebook event '%s' for pixel %s.", event_name, integration.pixel_id)
        if _should_db_log(event_name, "failed"):
            _try_log_store_event(
                store_public_id=store_public_id,
                event_name=event_name,
                status="failed",
                message="request_failed",
                metadata={
                    "event_id": eid,
                    "pixel_id": getattr(integration, "pixel_id", "") or "",
                },
            )
        if raise_on_error:
            raise
        return
    else:
        try:
            cache.set(dedup_key, "1", 60 * 60 * 24)
        except Exception:
            pass
        if _should_db_log(event_name, "success"):
            md = {"event_id": eid, "pixel_id": getattr(integration, "pixel_id", "") or ""}
            if isinstance(event_data, dict):
                if "value" in event_data:
                    md["value"] = event_data.get("value")
                if "currency" in event_data:
                    md["currency"] = event_data.get("currency")
                if "order_id" in event_data:
                    md["order_id"] = event_data.get("order_id")
            _try_log_store_event(
                store_public_id=store_public_id,
                event_name=event_name,
                status="success",
                message="",
                metadata=md,
            )


def track_purchase(request, order, event_id: str, integration) -> None:
    user_data = _extract_user_data(request)

    email = getattr(order, "email", "") or ""
    if email:
        user_data["em"] = [_hash_value(email)]

    phone = getattr(order, "phone", "") or ""
    if phone:
        user_data["ph"] = [_hash_value(phone)]

    # Purchase fires when the storefront successfully creates an order (typically pending).
    # Do not gate on merchant confirmation — that would duplicate if we also sent on status change.

    event_data = build_purchase_custom_data(order)

    _send_event(
        integration,
        "Purchase",
        event_data,
        user_data,
        event_id=event_id,
        store_public_id=getattr(getattr(order, "store", None), "public_id", "") or "",
    )


def track_initiate_checkout(request, event_id: str, integration) -> None:
    user_data = _extract_user_data(request)
    _send_event(
        integration,
        "InitiateCheckout",
        {},
        user_data,
        event_id=event_id,
        store_public_id=getattr(getattr(request, "store", None), "public_id", "") or "",
    )


def track_view_content(request, product, event_id: str, integration) -> None:
    user_data = _extract_user_data(request)
    event_data = build_view_content_custom_data(product, store=getattr(request, "store", None))
    _send_event(
        integration,
        "ViewContent",
        event_data,
        user_data,
        event_id=event_id,
        store_public_id=getattr(getattr(request, "store", None), "public_id", "") or "",
    )


def track_search(request, query: str, event_id: str, integration) -> None:
    user_data = _extract_user_data(request)
    event_data = {"search_string": query}
    _send_event(
        integration,
        "Search",
        event_data,
        user_data,
        event_id=event_id,
        store_public_id=getattr(getattr(request, "store", None), "public_id", "") or "",
    )


def send_capi_event_payload(
    *,
    store_public_id: str,
    integration,
    event_name: str,
    event_id: str,
    payload: dict[str, Any],
) -> None:
    """
    Task-safe entrypoint: send an event using pre-built payload.

    payload shape:
      {"event_id": str, "user_data": {...}, "custom_data": {...}, "metadata": {...}}
    """
    user_data = payload.get("user_data") if isinstance(payload, dict) else None
    if not isinstance(user_data, dict):
        user_data = {}
    custom_data = payload.get("custom_data") if isinstance(payload, dict) else None
    if not isinstance(custom_data, dict):
        custom_data = {}

    _send_event(
        integration,
        event_name,
        custom_data,
        user_data,
        event_id=event_id,
        store_public_id=store_public_id,
        raise_on_error=True,
    )
