from __future__ import annotations

from config.celery import app
from engine.apps.stores.models import Store
from engine.core.tenant_execution import system_scope

from .cache_sync import sync_product_stock_cache


def _fanout_product_stock_cache_sync() -> None:
    """Enqueue ``sync_product_stock_cache_for_store`` once per store."""
    with system_scope(reason="schedule_product_stock_cache_all_stores"):
        for sid in Store.objects.order_by("id").values_list("id", flat=True).iterator(chunk_size=500):
            sync_product_stock_cache_for_store.delay(int(sid))


@app.task(
    name="engine.apps.inventory.sync_product_stock_cache_for_store",
    soft_time_limit=510,
    time_limit=600,
)
def sync_product_stock_cache_for_store(store_id: int) -> None:
    with system_scope(reason="sync_product_stock_cache_for_store"):
        sync_product_stock_cache(int(store_id))


@app.task(
    name="engine.apps.inventory.schedule_product_stock_cache_all_stores",
    soft_time_limit=120,
    time_limit=150,
)
def schedule_product_stock_cache_all_stores() -> None:
    """Beat entrypoint: enqueue one bounded worker task per store."""
    _fanout_product_stock_cache_sync()


@app.task(
    name="engine.apps.inventory.sync_product_stock_cache_all_stores",
    soft_time_limit=120,
    time_limit=150,
)
def sync_product_stock_cache_all_stores() -> None:
    """
    Backward compatibility for django-celery-beat rows that still use this task path.

    Prefer ``schedule_product_stock_cache_all_stores`` for new periodic tasks.
    """
    _fanout_product_stock_cache_sync()
