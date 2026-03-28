from django.urls import path

from .promotion_views import BulkDiscountStorefrontListView

urlpatterns = [
    path(
        "bulk-discounts/",
        BulkDiscountStorefrontListView.as_view(),
        name="storefront-bulk-discounts",
    ),
]
