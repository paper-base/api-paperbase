from django.urls import path

from . import storefront_views

urlpatterns = [
    path("public/", storefront_views.StorePublicView.as_view(), name="store-public"),
]
