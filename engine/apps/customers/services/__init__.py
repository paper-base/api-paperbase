"""
Customer domain services. Purchase truth lives in ``purchase_service``; list UIs
may read denormalized ``Customer`` rollups for performance (see model docstring).
"""

from engine.apps.customers.services.purchase_service import (
    CustomerPurchaseMetrics,
    annotate_queryset_list_purchase_metrics,
    get_confirmed_orders,
    get_confirmed_orders_for_store,
    get_customer_purchase_metrics,
)

__all__ = [
    "CustomerPurchaseMetrics",
    "annotate_queryset_list_purchase_metrics",
    "get_confirmed_orders",
    "get_confirmed_orders_for_store",
    "get_customer_purchase_metrics",
]
