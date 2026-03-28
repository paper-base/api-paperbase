from django.urls import path

from . import views

urlpatterns = [
    path("filters/", views.CatalogFiltersView.as_view(), name="catalog-filters"),
]
