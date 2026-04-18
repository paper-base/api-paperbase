# IMPORTANT: Only Order.status=CONFIRMED is valid for customer and store purchase
# business metrics. Do not use the purchase ledger, pending orders, or ad-hoc
# Order filters for these totals — use the functions in this module only.
#
# PurchaseLedgerEntry is audit / line history only.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db.models import (
    Q,
    QuerySet,
    Count,
    Max,
    Min,
    Sum,
    Value,
    DecimalField,
)
from django.db.models.functions import Coalesce

from engine.apps.customers.models import Customer
from engine.apps.orders.models import Order
from engine.apps.stores.models import Store


def get_confirmed_orders(customer: Customer | None) -> QuerySet[Order]:
    """
    Canonical Order queryset for per-customer business metrics: same store, same
    customer, status CONFIRMED. This is the only allowed base queryset for
    per-customer purchase counts, spend, and AOV from Order rows.

    If ``customer`` is None, returns an empty queryset.
    """
    if customer is None:
        return Order.objects.none()
    return Order.objects.filter(
        store_id=customer.store_id,
        customer_id=customer.pk,
        status=Order.Status.CONFIRMED,
    )


def get_confirmed_orders_for_store(store: Store) -> QuerySet[Order]:
    """
    All confirmed orders for a store (dashboard revenue / order volume).
    Not a different definition of "confirmed" — only store-wide scope.
    """
    return Order.objects.filter(
        store_id=store.pk,
        status=Order.Status.CONFIRMED,
    )


@dataclass(frozen=True)
class CustomerPurchaseMetrics:
    """Aggregates derived only from ``get_confirmed_orders`` (Order CONFIRMED)."""

    total_orders: int
    total_spent: Decimal
    first_order_at: datetime | None
    last_order_at: datetime | None
    average_order_value: Decimal
    loyalty_score: Decimal


def get_customer_purchase_metrics(customer: Customer) -> CustomerPurchaseMetrics:
    """
    Canonical purchase metrics for a customer from confirmed orders only.
    Spend uses ``subtotal_after_discount`` (merchandise after discount), matching
    rollups written in ``_apply_customer_rollup_on_status_change``.

    Date bounds use each order's ``created_at`` (when the order was placed).
    """
    qs = get_confirmed_orders(customer)
    agg = qs.aggregate(
        total_orders=Count("id"),
        total_spent=Sum("subtotal_after_discount"),
        first_order_at=Min("created_at"),
        last_order_at=Max("created_at"),
    )
    count = int(agg["total_orders"] or 0)
    spent = agg["total_spent"] if agg["total_spent"] is not None else Decimal("0.00")
    if not isinstance(spent, Decimal):
        spent = Decimal(str(spent))
    aov = (spent / count) if count else Decimal("0.00")
    loyalty = (Decimal(count) * Decimal("2")) + (spent / Decimal("100"))
    return CustomerPurchaseMetrics(
        total_orders=count,
        total_spent=spent,
        first_order_at=agg["first_order_at"],
        last_order_at=agg["last_order_at"],
        average_order_value=aov,
        loyalty_score=loyalty,
    )


# Annotation names; same filters as get_customer_purchase_metrics (confirmed orders only).
ANNOTATION_PREFIX = "confirmed_purchase"
CONFIRMED_ORDER_COUNT = f"{ANNOTATION_PREFIX}_order_count"
CONFIRMED_SPENT = f"{ANNOTATION_PREFIX}_spent"
CONFIRMED_FIRST_AT = f"{ANNOTATION_PREFIX}_first_order_at"
CONFIRMED_LAST_AT = f"{ANNOTATION_PREFIX}_last_order_at"


def annotate_queryset_list_purchase_metrics(
    customer_qs: QuerySet[Customer],
) -> QuerySet[Customer]:
    """
    Attach confirmed-order rollups in one query for list endpoints so values match
    ``get_customer_purchase_metrics`` (and the customer ``details`` action) without
    N+1 queries. Does not use denormalized ``Customer.total_*`` columns.
    """
    f = Q(orders__status=Order.Status.CONFIRMED)
    return customer_qs.annotate(
        **{
            CONFIRMED_ORDER_COUNT: Count("orders", filter=f),
            CONFIRMED_SPENT: Coalesce(
                Sum("orders__subtotal_after_discount", filter=f),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
            CONFIRMED_FIRST_AT: Min("orders__created_at", filter=f),
            CONFIRMED_LAST_AT: Max("orders__created_at", filter=f),
        }
    )
