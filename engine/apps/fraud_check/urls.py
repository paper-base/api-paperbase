from django.urls import path

from .views import FraudCheckView

urlpatterns = [
    path("", FraudCheckView.as_view(), name="fraud-check"),
]

