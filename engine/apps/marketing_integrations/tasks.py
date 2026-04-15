from __future__ import annotations

from datetime import timedelta
from typing import Any

from config.celery import app
from django.utils import timezone


_EVENT_NAME_TO_FLAG: dict[str, str] = {
    "Purchase": "track_purchase",
    "InitiateCheckout": "track_initiate_checkout",
    "ViewContent": "track_view_content",
    "Search": "track_search",
}


@app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    acks_late=True,
    name="engine.apps.marketing_integrations.send_capi_event",
)
def send_capi_event(
    self,
    store_public_id: str,
    event_name: str,
    event_id: str,
    payload: dict[str, Any],
) -> None:
    """
    Send a Meta CAPI event for a store asynchronously.

    IMPORTANT:
    - store_public_id is the only tenant identifier accepted here (no DB ids).
    - Store and MarketingIntegration are re-fetched inside the worker for strict isolation.
    """
    from engine.apps.marketing_integrations.models import MarketingIntegration
    from engine.apps.marketing_integrations.services import facebook_service
    from engine.apps.stores.models import Store

    spid = (store_public_id or "").strip()
    if not spid:
        return

    store = Store.objects.filter(public_id=spid).first()
    if not store:
        return

    integrations = (
        MarketingIntegration.objects.filter(store=store, is_active=True)
        .select_related("event_settings")
        .all()
    )

    for integration in integrations:
        if integration.provider != "facebook":
            continue
        event_flag = _EVENT_NAME_TO_FLAG.get(event_name or "")
        settings = getattr(integration, "event_settings", None)
        if event_flag and settings is not None and getattr(settings, event_flag, True) is False:
            continue
        facebook_service.send_capi_event_payload(
            store_public_id=store.public_id,
            integration=integration,
            event_name=event_name,
            event_id=event_id,
            payload=payload or {},
        )


@app.task(name="engine.apps.marketing_integrations.cleanup_old_event_logs")
def cleanup_old_event_logs() -> int:
    """Celery beat: delete StoreEventLog rows older than 7 days."""
    from engine.apps.marketing_integrations.models import StoreEventLog

    cutoff = timezone.now() - timedelta(days=7)
    qs = StoreEventLog.objects.filter(created_at__lt=cutoff)
    deleted, _ = qs.delete()
    return int(deleted or 0)

