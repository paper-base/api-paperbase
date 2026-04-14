from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import DenyAPIKeyAccess, IsDashboardUser
from engine.apps.stores.models import StoreMembership
from engine.core.tenancy import get_active_store
from engine.core.tenant_drf import ProvenTenantContextMixin

from .serializers import FraudCheckRequestSerializer
from .services import run_fraud_check


class FraudCheckView(ProvenTenantContextMixin, APIView):
    permission_classes = [DenyAPIKeyAccess, IsDashboardUser]

    def post(self, request):
        serializer = FraudCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ctx = get_active_store(request)
        if not ctx.store or not ctx.membership:
            return Response({"detail": "No active store."}, status=status.HTTP_403_FORBIDDEN)
        if ctx.membership.role != StoreMembership.Role.OWNER:
            return Response(
                {"detail": "Only the store owner can run fraud checks."},
                status=status.HTTP_403_FORBIDDEN,
            )

        result = run_fraud_check(store=ctx.store, phone=serializer.validated_data["phone"])
        if result.limit_exceeded:
            return Response(result.response_json, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if result.status == "in_progress":
            return Response(result.response_json, status=status.HTTP_409_CONFLICT)
        return Response(
            {
                "cached": result.cached,
                "status": result.status,
                "log_id": result.log_id,
                "response": result.response_json,
            }
        )

