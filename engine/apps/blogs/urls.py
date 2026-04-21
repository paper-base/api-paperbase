from django.urls import path

from . import views

urlpatterns = [
    path("", views.PublicBlogListView.as_view(), name="public-blog-list"),
    path("<str:public_id>/", views.PublicBlogDetailView.as_view(), name="public-blog-detail"),
]
