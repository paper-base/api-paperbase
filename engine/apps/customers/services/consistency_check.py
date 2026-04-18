"""Debug validation: compare cached Customer rollups to canonical Order metrics."""

from __future__ import annotations

import logging
from decimal import Decimal

from engine.apps.customers.models import Customer
from engine.apps.customers.services.purchase_service import get_customer_purchase_metrics

logger = logging.getLogger(__name__)

_SPENT_Q = Decimal("0.01")


def validate_customer_purchase_consistency(customer: Customer) -> bool:
    """
    Compare denormalized ``Customer.total_orders`` / ``total_spent`` to values
    recomputed from confirmed orders (``get_customer_purchase_metrics``).

    Logs a warning and returns False on mismatch. Intended for management
    commands, tests, or manual debugging — not for hot read paths.
    """
    m = get_customer_purchase_metrics(customer)
    c_orders = int(customer.total_orders or 0)
    c_spent = (customer.total_spent or Decimal("0.00")).quantize(_SPENT_Q)
    m_spent = m.total_spent.quantize(_SPENT_Q)
    ok = True
    if m.total_orders != c_orders:
        ok = False
        logger.warning(
            "Customer purchase count mismatch: customer=%s store=%s "
            "cached_total_orders=%s confirmed_order_count=%s",
            customer.public_id,
            customer.store_id,
            c_orders,
            m.total_orders,
        )
    if m_spent != c_spent:
        ok = False
        logger.warning(
            "Customer total_spent mismatch: customer=%s store=%s "
            "cached_total_spent=%s confirmed_sum_subtotal=%s",
            customer.public_id,
            customer.store_id,
            c_spent,
            m_spent,
        )
    return ok
