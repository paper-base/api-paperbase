from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from engine.core.admin_dashboard_cache import (
    bump_dashboard_stats_cache_version,
    invalidate_dashboard_live_cache,
)
from engine.core.realtime import emit_store_events

from .models import Category, Product
from .services import invalidate_category_cache, invalidate_product_cache


@receiver(post_save, sender=Product)
def product_realtime_events(sender, instance, created, **kwargs):
    events = ["product_updated", "product.created"] if created else ["product_updated", "product.updated"]
    emit_store_events(
        instance.store.public_id,
        events,
        {"product_public_id": instance.public_id},
    )
    invalidate_dashboard_live_cache(instance.store.public_id)
    bump_dashboard_stats_cache_version(instance.store.public_id)
    invalidate_product_cache(instance.store.public_id)


@receiver(post_delete, sender=Product)
def product_delete_invalidate_dashboard(sender, instance, **kwargs):
    invalidate_dashboard_live_cache(instance.store.public_id)
    bump_dashboard_stats_cache_version(instance.store.public_id)
    invalidate_product_cache(instance.store.public_id)


@receiver(post_save, sender=Category)
def category_save_invalidate_cache(sender, instance, **kwargs):
    invalidate_category_cache(instance.store.public_id)


@receiver(post_delete, sender=Category)
def category_delete_invalidate_cache(sender, instance, **kwargs):
    invalidate_category_cache(instance.store.public_id)
