"""
Marketing / Meta Conversions API tracking facade.

Delegates to the marketing_integrations dispatcher. Import as ``meta_conversions``
from storefront views (orders, products, support, search).
"""

from engine.apps.marketing_integrations.services import dispatcher


class AnalyticsService:
    """Thin proxy that forwards every call to the marketing dispatcher."""

    def track_product_detail_view(self, request, product):
        dispatcher.track_product_detail_view(request, product)

    def track_search(self, request, query: str):
        dispatcher.track_search(request, query)

    def track_checkout_started(self, request) -> None:
        dispatcher.track_checkout_started(request)

    def track_order_created(self, request, order) -> None:
        dispatcher.track_order_created(request, order)

    def track_support_ticket_submitted(self, request) -> None:
        dispatcher.track_support_ticket_submitted(request)


# Module-level singleton — import as meta_conversions across the codebase.
meta_conversions = AnalyticsService()
