from django.urls import path

from .views import StorefrontHomeSectionsView

urlpatterns = [
    path("home/", StorefrontHomeSectionsView.as_view(), name="storefront-home-sections"),
]

