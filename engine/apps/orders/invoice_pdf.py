from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from engine.apps.orders.models import Order, OrderAddress, OrderItem
from engine.apps.orders.services import resolve_order_prepayment_type


@dataclass(frozen=True)
class InvoicePdfPayload:
    order: Order
    content: bytes
    filename: str


def _to_money(value: Decimal | None, currency: str) -> str:
    amount = value if value is not None else Decimal("0.00")
    return f"{currency} {amount:.2f}"


def _store_logo_data_uri(order: Order) -> str | None:
    logo = getattr(order.store, "logo", None)
    if not logo:
        return None
    try:
        logo.open("rb")
        raw = logo.read()
    except Exception:
        return None
    finally:
        try:
            logo.close()
        except Exception:
            pass
    if not raw:
        return None
    ext = (logo.name.rsplit(".", 1)[-1] if "." in logo.name else "png").lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _formatted_created_at(order: Order) -> str:
    tz = timezone.get_default_timezone()
    dt = timezone.localtime(order.created_at, tz)
    return dt.strftime("%Y-%m-%d %H:%M")


def _order_address(order: Order, address_type: str) -> OrderAddress | None:
    for address in order.addresses.all():
        if address.address_type == address_type:
            return address
    return None


def _invoice_context(order: Order) -> dict:
    currency = (order.store.currency or "BDT").strip() or "BDT"
    billing = _order_address(order, OrderAddress.AddressType.BILLING)
    shipping = _order_address(order, OrderAddress.AddressType.SHIPPING)
    prepayment_type = resolve_order_prepayment_type(order)
    payment_due = order.payment_status != Order.PaymentStatus.VERIFIED
    items = []
    for index, item in enumerate(order.items.all(), start=1):
        sku = item.variant.sku if item.variant_id and item.variant else ""
        items.append(
            {
                "index": index,
                "name": item.product_name_snapshot,
                "sku": sku,
                "quantity": item.quantity,
                "unit_price": _to_money(item.unit_price, currency),
                "line_total": _to_money(item.line_total, currency),
            }
        )
    return {
        "store": order.store,
        "order": order,
        "customer": order.customer,
        "billing_address": billing,
        "shipping_address": shipping,
        "items": items,
        "currency": currency,
        "subtotal": _to_money(order.subtotal_after_discount, currency),
        "discount_total": _to_money(order.discount_total, currency),
        "shipping_cost": _to_money(order.shipping_cost, currency),
        "grand_total": _to_money(order.total, currency),
        "created_at": _formatted_created_at(order),
        "logo_data_uri": _store_logo_data_uri(order),
        "is_paid": not payment_due,
        "payment_due": payment_due,
        "prepayment_type": prepayment_type,
        "transaction_id": order.transaction_id,
        "payer_number": order.payer_number,
    }


def render_order_invoice_pdf(*, order: Order) -> InvoicePdfPayload:
    context = _invoice_context(order)
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Invoice #{order.order_number}")
    y -= 24

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Date: {context['created_at']}")
    y -= 16
    c.drawString(50, y, f"Customer: {order.customer}")
    y -= 16
    c.drawString(50, y, f"Payment Status: {'Paid' if context['is_paid'] else 'Due'}")
    y -= 24

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Items")
    y -= 16
    c.setFont("Helvetica", 10)

    for item in context["items"]:
        line = (
            f"{item['index']}. {item['name']} "
            f"(Qty: {item['quantity']}) - {item['line_total']}"
        )
        c.drawString(50, y, line[:120])
        y -= 14
        if y < 80:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, f"Subtotal: {context['subtotal']}")
    y -= 16
    c.drawString(50, y, f"Discount: {context['discount_total']}")
    y -= 16
    c.drawString(50, y, f"Shipping: {context['shipping_cost']}")
    y -= 16
    c.drawString(50, y, f"Total: {context['grand_total']}")
    c.save()

    pdf_bytes = pdf_buffer.getvalue()
    return InvoicePdfPayload(
        order=order,
        content=pdf_bytes,
        filename=f"invoice_{order.order_number}.pdf",
    )


def fetch_order_for_invoice(*, order_id) -> Order:
    return (
        Order.objects.select_related("store", "customer")
        .prefetch_related(
            "addresses",
            "items",
            "items__variant",
            "items__product",
        )
        .get(id=order_id)
    )
