from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from config.permissions import IsStorefrontAPIKey
from engine.apps.products.views import StorefrontTenantMixin
from engine.core.tenancy import get_active_store

from .serializers import PublicBannerSerializer
from . import services


class PublicBannerListView(StorefrontTenantMixin, ListAPIView):
    """
    Public list of active banners for the tenant resolved from Host (or X-Store-ID / JWT).
    """

    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True
    serializer_class = PublicBannerSerializer
    pagination_class = None
    access_scope = "storefront"

    def list(self, request, *args, **kwargs):
        ctx = get_active_store(request)
        data = services.get_active_banners(ctx.store, request)
        return Response(data)
