from django.urls import path

from .views import StorePopupView


urlpatterns = [
    path("", StorePopupView.as_view(), name="public-popup"),
]

