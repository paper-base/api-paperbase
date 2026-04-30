from django.urls import path

from . import views

urlpatterns = [
    path('', views.OrderCreateView.as_view(), name='order-create'),
    path('<str:public_id>/invoice/', views.OrderInvoiceView.as_view(), name='order-invoice'),
    path('<str:public_id>/invoice/status/', views.OrderInvoiceStatusView.as_view(), name='order-invoice-status'),
    path('<str:public_id>/invoice/stream/', views.order_invoice_stream, name='order-invoice-stream'),
    path(
        '<str:public_id>/payment/',
        views.OrderPaymentSubmitView.as_view(),
        name='order-payment-submit',
    ),
    path('<str:public_id>/', views.OrderDetailView.as_view(), name='order-detail'),
]
