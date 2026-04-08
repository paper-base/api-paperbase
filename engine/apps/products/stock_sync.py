"""Backward-compatible wrapper for centralized stock cache sync."""

from django.db import transaction

from engine.apps.inventory.cache_sync import refresh_product_stock_cache
from .models import Product


def sync_product_stock_from_variants(product_id) -> None:
    product = Product.objects.filter(pk=product_id).only("store_id", "id").first()
    if not product:
        return
    with transaction.atomic():
        refresh_product_stock_cache(store_id=int(product.store_id), product_id=product.id)
