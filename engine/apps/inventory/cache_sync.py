from __future__ import annotations

import logging

from django.db import transaction

from engine.apps.products.models import Product

from .models import Inventory
from .utils import clamp_stock

logger = logging.getLogger(__name__)


def sync_product_stock_cache(store_id: int) -> None:
    """
    Synchronize Product.stock cache field from Inventory.quantity.

    Source of truth is Inventory; Product.stock is a derived read cache.
    """
    with transaction.atomic():
        inventories = list(
            Inventory.objects.select_for_update()
            .select_related("variant")
            .filter(product__store_id=store_id)
        )
        products = list(Product.objects.select_for_update().filter(store_id=store_id))

        product_expected: dict = {p.id: 0 for p in products}

        for inv in inventories:
            if inv.variant_id and not inv.variant.is_active:
                continue
            pid = inv.product_id
            qty = clamp_stock(inv.quantity or 0)
            product_expected[pid] = product_expected.get(pid, 0) + qty

        changed_products = []
        for p in products:
            expected = clamp_stock(product_expected.get(p.id, 0))
            if int(p.stock) != expected:
                logger.warning(
                    "Stock cache mismatch for product",
                    extra={
                        "store_id": store_id,
                        "product_id": str(p.id),
                        "expected_stock": expected,
                        "actual_stock": int(p.stock),
                    },
                )
                p.stock = expected
                changed_products.append(p)

        if changed_products:
            Product.objects.bulk_update(changed_products, ["stock"])
