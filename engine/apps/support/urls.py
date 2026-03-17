from django.urls import path

from . import views

urlpatterns = [
    path("tickets/", views.SupportTicketCreateView.as_view(), name="support-ticket-create"),
]
