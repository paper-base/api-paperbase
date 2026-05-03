"""Celery task module for the stores app."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from engine.apps.stores.models import StoreSettings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    name="engine.stores.dispatch_storefront_webhook",
)
def dispatch_storefront_webhook(self, store_public_id: str, payload: dict[str, Any]) -> None:
    event = str(payload.get("event") or "")
    if not (store_public_id or "").strip():
        logger.warning(
            "storefront_webhook_skipped",
            extra={"reason": "empty_store_public_id", "store_public_id": store_public_id, "event": event},
        )
        return

    try:
        settings_obj = StoreSettings.objects.get(store__public_id=store_public_id)
    except StoreSettings.DoesNotExist:
        logger.error(
            "storefront_webhook_store_settings_missing",
            extra={"store_public_id": store_public_id, "event": event},
        )
        return

    storefront_url = (settings_obj.storefront_url or "").strip()
    revalidate_secret = (settings_obj.revalidate_secret or "").strip()
    if not storefront_url or not revalidate_secret:
        logger.debug(
            "storefront_webhook_skipped",
            extra={
                "reason": "missing_url_or_secret",
                "store_public_id": store_public_id,
                "event": event,
            },
        )
        return

    forward: dict[str, Any] = {**payload, "store_public_id": store_public_id}
    base = storefront_url.rstrip("/")
    url = f"{base}/api/revalidate"
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": revalidate_secret,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=forward, headers=headers)
            response.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        countdown = 5 * (2 ** self.request.retries)
        logger.warning(
            "storefront_webhook_retry",
            extra={
                "store_public_id": store_public_id,
                "event": event,
                "retries": self.request.retries,
                "countdown": countdown,
                "error": str(exc),
            },
        )
        try:
            raise self.retry(exc=exc, countdown=countdown) from exc
        except MaxRetriesExceededError:
            logger.error(
                "storefront_webhook_failed",
                extra={
                    "store_public_id": store_public_id,
                    "event": event,
                    "error": str(exc),
                },
            )
            return

    logger.info(
        "storefront_webhook_dispatched",
        extra={"store_public_id": store_public_id, "event": event, "url": url},
    )
