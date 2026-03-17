"""
Generic analytics integration stub for the engine.

This module intentionally contains no external integration logic so that
the engine works out of the box without any third‑party accounts or keys.
Projects that use this engine can replace this implementation with
provider‑specific tracking (Meta, Google, etc.).
"""


class AnalyticsService:
    """
    No-op analytics service.

    Methods are present to keep existing call sites working, but they do
    not send any data anywhere.
    """

    def track_view_content(self, request, product):
        return

    def track_search(self, request, query: str):
        return

    def track_add_to_cart(self, request, product, quantity: int) -> None:
        return

    def track_add_to_wishlist(self, request, product) -> None:
        return

    def track_initiate_checkout(self, request) -> None:
        return

    def track_add_payment_info(self, request, order_data: dict | None = None) -> None:
        return

    def track_purchase(self, request, order) -> None:
        return

    def track_contact(self, request) -> None:
        return


# Module-level singleton — kept as meta_conversions for backward compatibility.
meta_conversions = AnalyticsService()
