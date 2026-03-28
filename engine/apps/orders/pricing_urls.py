from django.urls import path

from .pricing_preview_views import PricingPreviewView

urlpatterns = [
    path("preview/", PricingPreviewView.as_view(), name="pricing-preview"),
]
