from rest_framework.routers import DefaultRouter

from .views import StoreViewSet, StoreMembershipViewSet, StoreSettingsViewSet

router = DefaultRouter()
router.register(r"", StoreViewSet, basename="stores")
router.register(r"memberships", StoreMembershipViewSet, basename="store-memberships")
router.register(r"settings", StoreSettingsViewSet, basename="store-settings")

urlpatterns = router.urls

