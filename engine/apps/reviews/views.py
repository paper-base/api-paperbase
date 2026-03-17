from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer


class ReviewListByProductView(ListAPIView):
    """List approved reviews for a product. GET /api/v1/reviews/?product_id=<uuid>"""
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        if not product_id:
            return Review.objects.none()
        return Review.objects.filter(
            product_id=product_id,
            status=Review.Status.APPROVED,
        ).select_related('user').order_by('-created_at')


class ReviewCreateView(CreateAPIView):
    """Create a review (authenticated)."""
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewRatingSummaryView(APIView):
    """GET /api/v1/reviews/summary/?product_id=<uuid> -> { average_rating, count }"""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'average_rating': None, 'count': 0})
        agg = Review.objects.filter(
            product_id=product_id,
            status=Review.Status.APPROVED,
        ).aggregate(avg=Avg('rating'), count=Count('id'))
        return Response({
            'average_rating': round(agg['avg'], 2) if agg['avg'] is not None else None,
            'count': agg['count'] or 0,
        })
