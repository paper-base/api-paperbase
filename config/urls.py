from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
import logging
from time import perf_counter

from engine.core.storefront_search_views import StorefrontSearchView

logger = logging.getLogger(__name__)

def health(_request):
    start = perf_counter()
    logger.info("HEALTH HIT")
    elapsed_ms = (perf_counter() - start) * 1000
    logger.info("HEALTH RESPONSE TIME: %.2f ms", elapsed_ms)
    return JsonResponse({"status": "ok"})


def api_home(_request):
    return HttpResponse("home of paperbase API", content_type="text/plain")


def not_found(_request, exception):
    return HttpResponse("Not Found", content_type="text/plain")


from engine.apps.products.urls import category_urlpatterns
# API v1: all public and admin endpoints under /api/v1/
api_v1_patterns = [
    path('auth/', include('engine.apps.accounts.urls')),
    path('admin/', include('config.admin_urls')),
    path('settings/network/', include('engine.apps.stores.network_urls')),
    path('stores/', include('engine.apps.stores.urls')),
    path('store/', include('engine.apps.stores.storefront_urls')),
    path('products/', include('engine.apps.products.urls')),
    path('catalog/', include('engine.apps.products.catalog_urls')),
    path('categories/', include(category_urlpatterns)),
    path('banners/', include('engine.apps.banners.urls')),
    path('orders/', include('engine.apps.orders.urls')),
    path('shipping/', include('engine.apps.shipping.urls')),
    path('pricing/', include('engine.apps.orders.pricing_urls')),
    path('customers/', include('engine.apps.customers.urls')),
    path('notifications/', include('engine.apps.notifications.urls')),
    path('system-notifications/', include('engine.apps.notifications.system_urls')),
    path('support/', include('engine.apps.support.urls')),
    path('search/', StorefrontSearchView.as_view(), name='storefront-search'),
]

urlpatterns = [
    path("", api_home),
    path("health", health),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path('api/v1/', include(api_v1_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "config.urls.not_found"
