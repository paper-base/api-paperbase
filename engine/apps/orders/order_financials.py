"""Immutable order line snapshots and order-level rollup (Decimal, single source for persisted orders)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from engine.apps.products.models import Product, ProductVariant
from engine.apps.products.variant_utils import unit_price_for_line
from engine.apps.shipping.service import quote_shipping

MONEY_QUANT = Decimal("0.01")


def money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT)


def reference_unit_price(product: Product | None, variant: ProductVariant | None) -> Decimal:
    """
    List/reference unit price at snapshot time: product.original_price if set, else catalog sell price.
    """
    if product is None:
        return Decimal("0.00")
    sold = money(unit_price_for_line(product, variant))
    if product.original_price is not None:
        return money(product.original_price)
    return sold


def compute_line_financials(
    *,
    product: Product | None,
    variant: ProductVariant | None,
    quantity: int,
    unit_price: Decimal,
) -> dict[str, Decimal]:
    q = max(0, int(quantity))
    if product is None:
        unit = money(unit_price)
        return {
            "original_price": unit,
            "unit_price": unit,
            "discount_amount": Decimal("0.00"),
            "line_subtotal": money(unit * q),
            "line_total": money(unit * q),
        }
    ref = reference_unit_price(product, variant)
    unit = money(unit_price)
    disc = money(ref - unit)
    return {
        "original_price": ref,
        "unit_price": unit,
        "discount_amount": disc,
        "line_subtotal": money(ref * q),
        "line_total": money(unit * q),
    }


def aggregate_order_item_snapshots(items: list[Any]) -> tuple[Decimal, Decimal, Decimal]:
    """Return (subtotal_before_discount, discount_total, subtotal_after_discount) from persisted lines."""
    sb = Decimal("0.00")
    dt = Decimal("0.00")
    sa = Decimal("0.00")
    for oi in items:
        q = int(oi.quantity)
        sb += money(oi.line_subtotal)
        dt += money(oi.discount_amount * q)
        sa += money(oi.line_total)
    return money(sb), money(dt), money(sa)


def quote_shipping_for_order(
    *,
    store,
    subtotal_after_discount: Decimal,
    shipping_zone_pk: int | None,
    shipping_method_pk: int | None,
):
    return quote_shipping(
        store=store,
        order_subtotal=money(subtotal_after_discount),
        shipping_zone_pk=shipping_zone_pk,
        shipping_method_pk=shipping_method_pk,
    )


def build_pricing_snapshot_dict(
    *,
    subtotal_before_discount: Decimal,
    discount_total: Decimal,
    subtotal_after_discount: Decimal,
    shipping_cost: Decimal,
    total: Decimal,
    lines: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "subtotal_before_discount": str(money(subtotal_before_discount)),
        "discount_total": str(money(discount_total)),
        "subtotal_after_discount": str(money(subtotal_after_discount)),
        "shipping_cost": str(money(shipping_cost)),
        "total": str(money(total)),
        "lines": lines,
    }


def preview_lines_to_accounting(
    *,
    store,
    resolved_lines: list[dict[str, Any]],
    shipping_zone_pk: int | None,
    shipping_method_pk: int | None,
) -> dict[str, Any]:
    """
    resolved_lines: each dict has product (Product), variant (ProductVariant|None), quantity (int), unit_price (Decimal).
    Returns API-shaped dict with order rollups + line snapshots (string decimals).
    """
    line_payloads: list[dict[str, Any]] = []
    snapshots: list[dict[str, Decimal]] = []
    for row in resolved_lines:
        product = row["product"]
        variant = row.get("variant")
        qty = int(row["quantity"])
        unit = money(row["unit_price"])
        fin = compute_line_financials(product=product, variant=variant, quantity=qty, unit_price=unit)
        snapshots.append(fin)
        pid = str(product.public_id) if product else ""
        line_payloads.append(
            {
                "product_public_id": pid,
                "quantity": qty,
                "unit_price": str(fin["unit_price"]),
                "original_price": str(fin["original_price"]),
                "discount_amount": str(fin["discount_amount"]),
                "line_subtotal": str(fin["line_subtotal"]),
                "line_total": str(fin["line_total"]),
            }
        )

    sb = money(sum(f["line_subtotal"] for f in snapshots))
    dt = Decimal("0.00")
    for row, fin in zip(resolved_lines, snapshots, strict=True):
        dt += money(fin["discount_amount"] * int(row["quantity"]))
    dt = money(dt)
    sa = money(sum(f["line_total"] for f in snapshots))

    quote = quote_shipping_for_order(
        store=store,
        subtotal_after_discount=sa,
        shipping_zone_pk=shipping_zone_pk,
        shipping_method_pk=shipping_method_pk,
    )
    ship = money(quote.shipping_cost)
    tot = money(sa + ship)

    return {
        "subtotal_before_discount": str(sb),
        "discount_total": str(dt),
        "subtotal_after_discount": str(sa),
        "shipping_cost": str(ship),
        "total": str(tot),
        "lines": line_payloads,
        "_shipping_zone": quote.zone,
        "_shipping_method": quote.method,
        "_shipping_rate": quote.rate,
    }
