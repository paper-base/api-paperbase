from rest_framework import status
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PaymentMethod
from .serializers import PaymentMethodSerializer, PaymentInitiateSerializer


class PaymentMethodListView(APIView):
    """List active payment methods (e.g. for checkout)."""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        methods = PaymentMethod.objects.filter(is_active=True)
        return Response(PaymentMethodSerializer(methods, many=True).data)


class PaymentInitiateView(APIView):
    """Placeholder: initiate a payment for an order. Integrate with Stripe/Razorpay etc. here."""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def post(self, request):
        ser = PaymentInitiateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        # TODO: create Payment record, call gateway, return client payload
        return Response(
            {'detail': 'Payment initiation not implemented. Plug in your gateway.'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
