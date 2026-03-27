"""Backward-compatible wrapper for centralized stock cache sync."""

from engine.apps.inventory.cache_sync import sync_product_stock_cache
from .models import Product


def sync_product_stock_from_variants(product_id) -> None:
    product = Product.objects.filter(pk=product_id).only("store_id").first()
    if not product:
        return
    sync_product_stock_cache(int(product.store_id))
