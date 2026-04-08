from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.permissions import DenyAPIKeyAccess, IsAdminUser
from engine.core.search_serializers import UnifiedSearchResponseSerializer
from engine.core.search_services import search as search_entities
from engine.core.tenancy import get_active_store
from engine.core.tenant_drf import ProvenTenantContextMixin


class UnifiedSearchView(ProvenTenantContextMixin, APIView):
    permission_classes = [DenyAPIKeyAccess, IsAdminUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "heavy_search"

    def get(self, request):
        query = (request.query_params.get("query") or "").strip()
        if not query:
            serializer = UnifiedSearchResponseSerializer(
                {"products": [], "orders": [], "customers": [], "tickets": []}
            )
            return Response(serializer.data)

        ctx = get_active_store(request)
        if not ctx.store:
            return Response(
                {"detail": "Tenant (store) context is required"},
                status=400,
            )

        data = search_entities(query=query, store=ctx.store, per_type_limit=10)
        serializer = UnifiedSearchResponseSerializer(data)
        return Response(serializer.data)
