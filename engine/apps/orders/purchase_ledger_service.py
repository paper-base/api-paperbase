"""
Append-only **audit** ledger for line-level order history. Not a source of truth
for revenue, order counts, or customer LTV; use
``engine.apps.customers.services.purchase_service`` for business metrics.
All mutations are append-only via model constraints.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model

from engine.apps.customers.models import Customer
from engine.core.ids import generate_public_id
from engine.apps.orders.models import (
    Order,
    OrderItem,
    PurchaseLedgerAdjustment,
    PurchaseLedgerEntry,
)

User = get_user_model()


def _json_decimal(d: Decimal) -> str:
    return str(d)


def append_ledger_line_for_order_item(
    *,
    order: Order,
    order_item: OrderItem,
    customer: Customer | None,
) -> tuple[PurchaseLedgerEntry, bool]:
    """
    Idempotent ledger append keyed by order_item.public_id.
    Returns (entry, created).
    """
    if order_item.order_id != order.pk:
        raise ValueError("order_item does not belong to order")
    if order.store_id != order_item.order.store_id:
        raise ValueError("order store mismatch")
    cust_pid = customer.public_id if customer else ""
    cust_pk = customer.pk if customer else None
    product_pid = order_item.product.public_id if order_item.product_id else ""
    variant_pid = order_item.variant.public_id if order_item.variant_id else None

    defaults = {
        "public_id": generate_public_id("purchaseledger"),
        "store_id": order.store_id,
        "customer_id": cust_pk,
        "customer_public_id": cust_pid,
        "order": order,
        "order_public_id": order.public_id,
        "order_number": order.order_number,
        "order_uuid": order.pk,
        "order_item": order_item,
        "product_public_id": product_pid,
        "variant_public_id": variant_pid,
        "product_name": order_item.product_name_snapshot,
        "variant_label": order_item.variant_snapshot or "",
        "quantity": int(order_item.quantity),
        "unit_price": order_item.unit_price,
        "line_total": order_item.line_total,
        "order_status_snapshot": order.status,
    }
    return PurchaseLedgerEntry.objects.get_or_create(
        order_item_public_id=order_item.public_id,
        defaults=defaults,
    )


def append_ledger_lines_for_order(*, order: Order) -> None:
    """Append ledger rows for all lines (idempotent per line)."""
    customer = order.customer
    items = OrderItem.objects.filter(order_id=order.pk)
    for oi in items:
        append_ledger_line_for_order_item(order=order, order_item=oi, customer=customer)


def record_purchase_adjustment(
    *,
    store_id: int,
    customer: Customer | None,
    order: Order,
    order_item_public_id: str,
    field_key: str,
    old_value: Any,
    new_value: Any,
    reason: str = "staff_dashboard_edit",
    created_by: User | None = None,
) -> PurchaseLedgerAdjustment:
    cust_pid = customer.public_id if customer else ""
    cust_pk = customer.pk if customer else None
    return PurchaseLedgerAdjustment.objects.create(
        store_id=store_id,
        customer_id=cust_pk,
        customer_public_id=cust_pid,
        order=order,
        order_public_id=order.public_id,
        order_item_public_id=order_item_public_id or "",
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        created_by=created_by,
    )


def order_item_line_snapshot(oi: OrderItem) -> dict[str, Any]:
    """Serializable snapshot for adjustment old_value (no live catalog reads required for meaning)."""
    return {
        "order_item_public_id": oi.public_id,
        "product_public_id": oi.product.public_id if oi.product_id else None,
        "variant_public_id": oi.variant.public_id if oi.variant_id else None,
        "product_name_snapshot": oi.product_name_snapshot,
        "variant_snapshot": oi.variant_snapshot,
        "quantity": int(oi.quantity),
        "unit_price": _json_decimal(oi.unit_price),
        "line_total": _json_decimal(oi.line_total),
    }
