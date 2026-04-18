"""Shared admin order list filters for HTTP list + CSV export (store-scoped)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q, QuerySet
from django.http import QueryDict
from django.utils import timezone

from engine.utils.bd_query import filter_by_bd_date
from engine.utils.time import bd_today

from .models import Order

ALLOWED_ORDER_STATUSES = {
    Order.Status.PENDING,
    Order.Status.PAYMENT_PENDING,
    Order.Status.CONFIRMED,
    Order.Status.CANCELLED,
}

ALLOWED_ORDER_FLAGS = {
    Order.Flag.NO_RESPONSE,
    Order.Flag.CALL_LATER,
    Order.Flag.WRONG_NUMBER,
    Order.Flag.BUSY,
    Order.Flag.HIGH_PRIORITY,
}

ALLOWED_ORDER_PAYMENT_STATUSES = {
    Order.PaymentStatus.NONE,
    Order.PaymentStatus.SUBMITTED,
    Order.PaymentStatus.VERIFIED,
    Order.PaymentStatus.FAILED,
}

# Keys accepted on export create (``select_all``); must stay aligned with admin list filters.
EXPORT_FILTER_KEYS = frozenset(
    {
        "status",
        "flag",
        "date_range",
        "payment_status",
        "search",
        "customer",
        "customer_public_id",
    }
)


def normalize_export_filters(raw: dict) -> dict:
    """Strip unknown keys; string-coerce values for JSON storage."""
    out: dict[str, str] = {}
    for key in EXPORT_FILTER_KEYS:
        if key not in raw:
            continue
        val = raw.get(key)
        if val is None or val == "":
            continue
        out[key] = str(val).strip()
    return out


def _param_get(query_params: QueryDict | None, filters: dict | None, key: str) -> str:
    if query_params is not None:
        return (query_params.get(key) or "").strip()
    if filters is None:
        return ""
    val = filters.get(key)
    if val is None:
        return ""
    return str(val).strip()


def apply_order_admin_filters(
    qs: QuerySet,
    *,
    query_params: QueryDict | None = None,
    filters: dict | None = None,
) -> QuerySet:
    """
    Apply the same filter rules as the admin order list.

    Pass exactly one of ``query_params`` or ``filters``.
    """
    if (query_params is None) == (filters is None):
        raise ValueError("Pass exactly one of query_params or filters")

    customer_public_id = _param_get(query_params, filters, "customer") or _param_get(
        query_params, filters, "customer_public_id"
    )
    if customer_public_id:
        qs = qs.filter(customer__public_id=customer_public_id)

    status_value = _param_get(query_params, filters, "status").lower()
    if status_value in ALLOWED_ORDER_STATUSES:
        qs = qs.filter(status=status_value)

    flag_value = _param_get(query_params, filters, "flag").lower()
    if flag_value in ALLOWED_ORDER_FLAGS:
        qs = qs.filter(flag=flag_value)

    date_range = _param_get(query_params, filters, "date_range").lower()
    if date_range == "today":
        qs = filter_by_bd_date(qs, "created_at", bd_today())
    elif date_range == "last_7_days":
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
    elif date_range == "last_30_days":
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=30))

    payment_status = _param_get(query_params, filters, "payment_status").lower()
    if payment_status in ALLOWED_ORDER_PAYMENT_STATUSES:
        qs = qs.filter(payment_status=payment_status)

    search = _param_get(query_params, filters, "search")
    if search:
        qs = qs.filter(
            Q(order_number__icontains=search)
            | Q(public_id__icontains=search)
            | Q(courier_consignment_id__icontains=search)
            | Q(transaction_id__icontains=search)
            | Q(shipping_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(customer__name__icontains=search)
        )

    return qs


def build_export_queryset(*, store_id: int, filters: dict | None) -> QuerySet:
    """Orders for CSV export: always pinned to ``store_id`` (for Celery / workers)."""
    qs = Order.objects.filter(store_id=store_id)
    return apply_order_admin_filters(qs, filters=filters or {}).order_by("-created_at", "id")
