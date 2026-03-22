from rest_framework.routers import DefaultRouter

from .domain_views import DomainViewSet
from .views import StoreMembershipViewSet, StoreSettingsViewSet, StoreViewSet

router = DefaultRouter()
router.register(r"domains", DomainViewSet, basename="store-domains")
router.register(r"", StoreViewSet, basename="stores")
router.register(r"memberships", StoreMembershipViewSet, basename="store-memberships")
router.register(r"settings", StoreSettingsViewSet, basename="store-settings")

urlpatterns = router.urls

