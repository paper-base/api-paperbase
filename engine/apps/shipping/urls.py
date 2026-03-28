from django.urls import path
from . import views

urlpatterns = [
    path('options/', views.ShippingOptionsView.as_view()),
    path('zones/', views.ShippingZonesView.as_view()),
    path('preview/', views.ShippingPreviewView.as_view()),
]
