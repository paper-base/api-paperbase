from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from engine.apps.analytics.service import meta_conversions
from engine.core.tenancy import get_active_store

from .models import SupportTicket
from .serializers import SupportTicketCreateSerializer, SupportTicketPublicResponseSerializer


class SupportTicketCreateView(APIView):
    """Submit support ticket (guest allowed). Tenant is resolved by Host (Option A)."""
    permission_classes = []  # allow unauthenticated
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        ctx = get_active_store(request)
        if not ctx.store:
            return Response(
                {"detail": "Unknown store. Use the store subdomain/domain to submit tickets."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = SupportTicketCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ticket: SupportTicket = ser.save(store=ctx.store)
        meta_conversions.track_support_ticket_submission(request)
        return Response(
            SupportTicketPublicResponseSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )
