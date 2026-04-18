from django.urls import path

from . import views

urlpatterns = [
    path('', views.OrderCreateView.as_view(), name='order-create'),
    path(
        '<str:public_id>/payment/',
        views.OrderPaymentSubmitView.as_view(),
        name='order-payment-submit',
    ),
    path('<str:public_id>/', views.OrderDetailView.as_view(), name='order-detail'),
]
