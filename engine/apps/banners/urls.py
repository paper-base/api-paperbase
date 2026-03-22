from django.urls import path

from . import views

urlpatterns = [
    path("", views.PublicBannerListView.as_view(), name="public-banner-list"),
]
