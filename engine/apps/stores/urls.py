from django.urls import path
from rest_framework.routers import DefaultRouter

from . import checkout_settings_views, storefront_views
from .views import StoreMembershipViewSet, StoreSettingsViewSet, StoreViewSet

router = DefaultRouter()
router.register(r"", StoreViewSet, basename="store")
router.register(r"memberships", StoreMembershipViewSet, basename="store-memberships")
router.register(r"settings", StoreSettingsViewSet, basename="store-settings")

urlpatterns = [
    path("public/", storefront_views.StorePublicView.as_view(), name="store-public"),
    path(
        "checkout-settings/",
        checkout_settings_views.StoreCheckoutSettingsView.as_view(),
        name="store-checkout-settings",
    ),
] + router.urls
