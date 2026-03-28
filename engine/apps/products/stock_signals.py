"""Storefront stock status helpers (threshold from StoreSettings)."""

from __future__ import annotations


def stock_status_for_quantity(quantity: int, low_threshold: int) -> str:
    if quantity <= 0:
        return "out_of_stock"
    if quantity < low_threshold:
        return "low"
    return "in_stock"


def get_low_stock_threshold(store) -> int:
    from engine.apps.stores.models import StoreSettings

    row = StoreSettings.objects.filter(store=store).only("low_stock_threshold").first()
    return int(row.low_stock_threshold) if row else 5
