from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from engine.core.tenancy import get_active_store

from .serializers import ReviewSerializer, ReviewCreateSerializer
from . import services


class ReviewListByProductView(ListAPIView):
    """List approved reviews for a product. GET /api/v1/reviews/?product_public_id=<public_id>"""
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        ctx = get_active_store(self.request)
        if not ctx.store:
            from .models import Review
            return Review.objects.none()
        return services.build_review_list_queryset(
            ctx.store, self.request.query_params
        )

    def list(self, request, *args, **kwargs):
        ctx = get_active_store(request)
        if not ctx.store:
            return Response({"count": 0, "results": []})
        cached = services.get_cached_review_list(
            ctx.store.public_id, request.query_params
        )
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        services.set_cached_review_list(
            ctx.store.public_id, request.query_params, response.data
        )
        return response


class ReviewCreateView(CreateAPIView):
    """Create a review (authenticated)."""
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewRatingSummaryView(APIView):
    """GET /api/v1/reviews/summary/?product_public_id=<public_id> -> { average_rating, count }"""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        ctx = get_active_store(request)
        if not ctx.store:
            raise NotFound()
        product_public_id = request.query_params.get('product_public_id')
        data = services.get_review_summary(ctx.store, product_public_id)
        if data is None:
            raise NotFound()
        return Response(data)
