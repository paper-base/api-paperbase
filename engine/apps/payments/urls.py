from django.urls import path
from . import views

urlpatterns = [
    path('methods/', views.PaymentMethodListView.as_view()),
    path('initiate/', views.PaymentInitiateView.as_view()),
]
