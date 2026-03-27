from __future__ import annotations

from config.celery import app
from engine.apps.stores.models import Store
from engine.core.tenant_execution import system_scope

from .cache_sync import sync_product_stock_cache


@app.task(name="engine.apps.inventory.sync_product_stock_cache_for_store")
def sync_product_stock_cache_for_store(store_id: int) -> None:
    with system_scope(reason="sync_product_stock_cache_for_store"):
        sync_product_stock_cache(int(store_id))


@app.task(name="engine.apps.inventory.sync_product_stock_cache_all_stores")
def sync_product_stock_cache_all_stores() -> None:
    with system_scope(reason="sync_product_stock_cache_all_stores"):
        for sid in Store.objects.values_list("id", flat=True):
            sync_product_stock_cache(int(sid))
