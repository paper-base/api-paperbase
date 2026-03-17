from django.urls import path
from . import views

urlpatterns = [
    path('', views.ReviewListByProductView.as_view()),
    path('create/', views.ReviewCreateView.as_view()),
    path('summary/', views.ReviewRatingSummaryView.as_view()),
]
