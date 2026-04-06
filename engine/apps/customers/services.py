"""
Customer analytics derived from the immutable purchase ledger.

Phase 2 (not implemented): PurchaseLedgerAdjustment rows are append-only audit records
and are NOT included in spend totals, order counts, or date ranges here. Integrating
corrections into reported totals would require an explicit product definition (e.g.
effective line totals) and is intentionally deferred.

Future: deprecate Customer.total_orders in favor of ledger-based counts; optional
materialized rollups for large stores.

Distinct order cardinality uses ledger.order_public_id (external order reference).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Max, Min, Sum

from engine.apps.customers.models import Customer
from engine.apps.orders.models import PurchaseLedgerEntry


@dataclass(frozen=True)
class CustomerLedgerAnalytics:
    historical_order_count: int
    total_spent: Decimal
    first_purchase_at: datetime | None
    last_purchase_at: datetime | None
    average_order_value: Decimal
    loyalty_score: Decimal


def get_customer_ledger_analytics(customer: Customer) -> CustomerLedgerAnalytics:
    """
    Aggregate purchase history for a store customer from PurchaseLedgerEntry only.
    Does not read Order, OrderItem, or Customer.total_orders.
    """
    qs = PurchaseLedgerEntry.objects.filter(
        store_id=customer.store_id,
        customer_id=customer.pk,
    )
    agg = qs.aggregate(
        historical_order_count=Count("order_public_id", distinct=True),
        total_spent=Sum("line_total"),
        first_purchase_at=Min("recorded_at"),
        last_purchase_at=Max("recorded_at"),
    )
    count = int(agg["historical_order_count"] or 0)
    spent = agg["total_spent"] if agg["total_spent"] is not None else Decimal("0.00")
    if not isinstance(spent, Decimal):
        spent = Decimal(str(spent))
    aov = (spent / count) if count else Decimal("0.00")
    loyalty = (Decimal(count) * Decimal("2")) + (spent / Decimal("100"))
    return CustomerLedgerAnalytics(
        historical_order_count=count,
        total_spent=spent,
        first_purchase_at=agg["first_purchase_at"],
        last_purchase_at=agg["last_purchase_at"],
        average_order_value=aov,
        loyalty_score=loyalty,
    )
