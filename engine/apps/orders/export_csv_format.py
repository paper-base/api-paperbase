"""
Pure string formatters for order CSV export (Asia/Dhaka wall time, addresses, Excel-safe phone).

``order_id`` is the order ``public_id`` (stable dashboard id). ``order_number`` is kept for
spreadsheet compatibility. All row values are strings for ``csv.writer``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils import timezone as django_timezone

from .models import Order, OrderAddress

DHAKA_TZ = ZoneInfo("Asia/Dhaka")

# Header row must match ``format_order_for_csv`` column order exactly.
ORDER_CSV_HEADERS = [
    "order_number",
    "order_id",
    "customer_name",
    "email",
    "phone",
    "full_address",
    "total_amount",
    "payment_status",
    "order_status",
    "created_at",
    "product_summary",
]


def convert_to_gmt6(dt: datetime | None) -> str:
    """
    Convert an instant to Asia/Dhaka wall time, strip microseconds, return ``YYYY-MM-DD HH:MM:SS``.

    Naive datetimes are interpreted as UTC (Django/Postgres convention for aware storage).
    """
    if dt is None:
        return ""
    if django_timezone.is_naive(dt):
        dt = django_timezone.make_aware(dt, dt_timezone.utc)
    local = dt.astimezone(DHAKA_TZ).replace(microsecond=0)
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _clean_csv_part(s: str) -> str:
    t = (s or "").strip()
    return t if t and t.lower() != "none" else ""


def format_full_address(order: Order) -> str:
    """
    Prefer structured shipping ``OrderAddress``; else ``shipping_address`` + ``district``.
    """
    shipping = None
    for addr in order.addresses.all():
        if addr.address_type == OrderAddress.AddressType.SHIPPING:
            shipping = addr
            break

    if shipping is not None:
        parts = [
            _clean_csv_part(shipping.address_line1),
            _clean_csv_part(shipping.address_line2),
            _clean_csv_part(shipping.city),
            _clean_csv_part(shipping.region),
            _clean_csv_part(shipping.postal_code),
            _clean_csv_part(shipping.country),
        ]
        out = ", ".join(p for p in parts if p)
        return re.sub(r",\s*,+", ", ", out).strip(", ").strip()

    line = _clean_csv_part(getattr(order, "shipping_address", "") or "")
    dist = _clean_csv_part(getattr(order, "district", "") or "")
    chunks: list[str] = []
    if line:
        chunks.append(line)
    if dist and dist not in line:
        chunks.append(dist)
    return ", ".join(chunks).strip()


def format_csv_phone(raw: str | None) -> str:
    """
    Phone as string only; preserve leading zeros. Tab-prefix when leading ``0`` so Excel
    opens the cell as text (avoids numeric coercion dropping the zero).
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    if s[0] == "0":
        return "\t" + s
    return s


def customer_name_for_csv(order: Order) -> str:
    if order.customer_id and order.customer:
        n = _clean_csv_part(order.customer.name or "")
        if n:
            return n
    return _clean_csv_part(getattr(order, "shipping_name", "") or "")


def product_summary_for_csv(order: Order) -> str:
    parts: list[str] = []
    for item in order.items.all():
        name = (item.product_name_snapshot or "").strip() or (
            item.product.name if item.product else "Unavailable"
        )
        vs = (item.variant_snapshot or "").strip()
        label = f"{name} ({vs}) x{item.quantity}" if vs else f"{name} x{item.quantity}"
        parts.append(label)
    return "; ".join(parts)


def format_order_for_csv(order: Order) -> list[str]:
    """Return one CSV row as strings only (same order as ``ORDER_CSV_HEADERS``)."""
    return [
        str(order.order_number or "").strip(),
        str(order.public_id or "").strip(),
        customer_name_for_csv(order),
        _clean_csv_part(order.email or ""),
        format_csv_phone(order.phone),
        format_full_address(order),
        str(order.total),
        str(order.payment_status or "").strip(),
        str(order.status or "").strip(),
        convert_to_gmt6(order.created_at),
        product_summary_for_csv(order),
    ]
