from django.urls import path

from . import views

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product-list'),
    path('search/', views.ProductSearchView.as_view(), name='product-search'),
    # Accept UUID or slug as identifier (frontend may use either)
    path('<str:identifier>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('<str:identifier>/related/', views.ProductRelatedView.as_view(), name='product-related'),
]

# Category URL patterns (hierarchical; top-level when parent omitted)
category_urlpatterns = [
    path('', views.CategoryListView.as_view(), name='category-list'),
    path('<slug:slug>/', views.CategoryDetailView.as_view(), name='category-detail'),
]
