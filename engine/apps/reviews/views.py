from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.core.tenancy import get_active_store
from engine.core.store_session import resolve_store_session

from .serializers import ReviewSerializer, ReviewCreateSerializer
from . import services


class ReviewListByProductView(ListAPIView):
    """List approved reviews for a product. GET /api/v1/reviews/?product_public_id=<public_id>"""
    serializer_class = ReviewSerializer
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True

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
    """Create a review (storefront API key)."""
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        request_ctx = get_active_store(self.request)
        store = request_ctx.store
        ctx["store"] = store
        session_ctx = resolve_store_session(self.request)
        ctx["store_session_id"] = session_ctx.store_session_id
        return ctx

    def perform_create(self, serializer):
        session_ctx = resolve_store_session(self.request)
        request_ctx = get_active_store(self.request)
        review = services.ReviewCreateService(self.request).create_review(
            store=request_ctx.store,
            store_session_id=session_ctx.store_session_id,
            user=self.request.user if self.request.user.is_authenticated else None,
            product=serializer.validated_data["product"],
            order_public_id=serializer.validated_data["order_public_id"],
            rating=serializer.validated_data["rating"],
            title=serializer.validated_data.get("title", ""),
            body=serializer.validated_data.get("body", ""),
            allow_legacy_binding=bool(serializer.validated_data.get("allow_legacy_binding", False)),
        )
        serializer.instance = review


class ReviewRatingSummaryView(APIView):
    """GET /api/v1/reviews/summary/?product_public_id=<public_id> -> { average_rating, count }"""
    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True

    def get(self, request):
        ctx = get_active_store(request)
        if not ctx.store:
            raise NotFound()
        product_public_id = request.query_params.get('product_public_id')
        data = services.get_review_summary(ctx.store, product_public_id)
        if data is None:
            raise NotFound()
        return Response(data)
