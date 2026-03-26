"""Cache-backed read service for storefront notification / CTA data."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from engine.core import cache_service

from .models import StorefrontCTA
from .serializers import NotificationSerializer


def get_active_notifications(store, request):
    """Return cached active storefront CTAs, falling back to DB."""
    key = cache_service.build_key(store.public_id, "notifications", "active")

    def fetcher():
        now = timezone.now()
        qs = StorefrontCTA.objects.filter(store=store, is_active=True).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now),
        )
        return NotificationSerializer(
            qs, many=True, context={"request": request}
        ).data

    return cache_service.get_or_set(key, fetcher, settings.CACHE_TTL_NOTIFICATIONS)


def invalidate_notification_cache(store_public_id: str) -> None:
    """Clear notification caches for a store."""
    cache_service.invalidate_store_resource(store_public_id, "notifications")
