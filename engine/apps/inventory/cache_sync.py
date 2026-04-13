from __future__ import annotations

import logging

from django.db import transaction

from engine.apps.products.models import Product

from .models import Inventory
from .utils import clamp_stock

logger = logging.getLogger(__name__)


def _contribution_from_inventory_row(inv: Inventory) -> int:
    """Per-row quantity counted toward Product.stock (inactive variants contribute 0)."""
    if inv.variant_id and not inv.variant.is_active:
        return 0
    return clamp_stock(inv.quantity or 0)


def total_stock_from_inventory_rows(inventories) -> int:
    """
    Aggregate Product.stock from inventory rows using the same rules as full-store sync:
    each row is clamped, summed per product, then the total is clamped.
    """
    total = 0
    for inv in inventories:
        total += _contribution_from_inventory_row(inv)
    return clamp_stock(total)


def refresh_product_stock_cache(*, store_id: int, product_id) -> None:
    """
    Recompute Product.stock from Inventory for one product.

    Locks Product, then all Inventory rows for that product (deterministic PK order).
    Must run inside transaction.atomic().
    """
    Product.objects.select_for_update().get(id=product_id, store_id=store_id)
    inv_rows = list(
        Inventory.objects.select_for_update()
        .prefetch_related("variant")
        .filter(product_id=product_id, product__store_id=store_id)
        .order_by("pk")
    )
    expected = total_stock_from_inventory_rows(inv_rows)
    Product.objects.filter(id=product_id, store_id=store_id).update(stock=expected)


def sync_product_stock_cache(store_id: int) -> None:
    """
    Synchronize Product.stock cache field from Inventory.quantity.

    Source of truth is Inventory; Product.stock is a derived read cache.
    """
    with transaction.atomic():
        inventories = list(
            Inventory.objects.select_for_update()
            .prefetch_related("variant")
            .filter(product__store_id=store_id)
        )
        products = list(Product.objects.select_for_update().filter(store_id=store_id))

        product_expected: dict = {p.id: 0 for p in products}

        for inv in inventories:
            pid = inv.product_id
            product_expected[pid] = product_expected.get(pid, 0) + _contribution_from_inventory_row(inv)

        changed_products = []
        for p in products:
            expected = clamp_stock(product_expected.get(p.id, 0))
            if int(p.stock) != expected:
                logger.info(
                    "Reconciled product stock cache from inventory (full store sync)",
                    extra={
                        "store_id": store_id,
                        "product_id": str(p.id),
                        "expected_stock": expected,
                        "previous_stock": int(p.stock),
                    },
                )
                p.stock = expected
                changed_products.append(p)

        if changed_products:
            Product.objects.bulk_update(changed_products, ["stock"])
