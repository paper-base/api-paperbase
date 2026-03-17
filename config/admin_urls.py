from django.urls import path, include
from rest_framework.routers import DefaultRouter

from engine.apps.orders.admin_views import AdminOrderViewSet
from engine.apps.products.admin_views import (
    AdminProductViewSet,
    AdminProductImageViewSet,
    AdminCategoryViewSet,
    AdminBrandViewSet,
)
from engine.apps.notifications.admin_views import AdminNotificationViewSet, AdminSystemNotificationViewSet
from engine.apps.support.admin_views import AdminContactSubmissionViewSet, AdminSupportTicketViewSet
from engine.apps.cart.admin_views import AdminCartViewSet
from engine.apps.wishlist.admin_views import AdminWishlistItemViewSet
from engine.core.admin_views import AdminActivityLogViewSet
from engine.apps.inventory.admin_views import AdminInventoryViewSet, AdminStockMovementViewSet

from .admin_api import DashboardStatsView, BrandingView, DashboardAnalyticsView

router = DefaultRouter()
router.register(r'orders', AdminOrderViewSet, basename='admin-orders')
router.register(r'products', AdminProductViewSet, basename='admin-products')
router.register(r'product-images', AdminProductImageViewSet, basename='admin-product-images')
router.register(r'categories', AdminCategoryViewSet, basename='admin-categories')
router.register(r'brands', AdminBrandViewSet, basename='admin-brands')
router.register(r'notifications', AdminNotificationViewSet, basename='admin-notifications')
router.register(r'system-notifications', AdminSystemNotificationViewSet, basename='admin-system-notifications')
router.register(r'contacts', AdminContactSubmissionViewSet, basename='admin-contacts')
router.register(r'support-tickets', AdminSupportTicketViewSet, basename='admin-support-tickets')
router.register(r'carts', AdminCartViewSet, basename='admin-carts')
router.register(r'wishlist', AdminWishlistItemViewSet, basename='admin-wishlist')
router.register(r'activities', AdminActivityLogViewSet, basename='admin-activities')
router.register(r'inventory', AdminInventoryViewSet, basename='admin-inventory')
router.register(r'stock-movements', AdminStockMovementViewSet, basename='admin-stock-movements')

urlpatterns = [
    path('stats/', DashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('analytics/overview/', DashboardAnalyticsView.as_view(), name='admin-dashboard-analytics'),
    path('branding/', BrandingView.as_view(), name='admin-branding'),
    path('', include(router.urls)),
]
