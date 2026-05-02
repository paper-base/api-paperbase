from django.urls import path

from .views import PresetsView, ThemeView

urlpatterns = [
    path("", ThemeView.as_view(), name="theming-theme"),
    path("presets/", PresetsView.as_view(), name="theming-presets"),
]
