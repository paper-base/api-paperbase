from django.urls import path

from .pricing_breakdown_views import PricingBreakdownView
from .pricing_preview_views import PricingPreviewView

urlpatterns = [
    path("preview/", PricingPreviewView.as_view(), name="pricing-preview"),
    path("breakdown/", PricingBreakdownView.as_view(), name="pricing-breakdown"),
]
