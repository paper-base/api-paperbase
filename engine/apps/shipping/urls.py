from django.urls import path
from . import views

urlpatterns = [
    path('options/', views.ShippingOptionsView.as_view()),
]
