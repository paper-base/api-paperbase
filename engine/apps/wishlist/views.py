from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.core.authentication import JWTAuthenticationAllowAPIKey
from engine.apps.analytics.service import meta_conversions
from engine.apps.products.models import Product
from engine.core.tenancy import require_api_key_store

from .models import WishlistItem
from .serializers import WishlistAddSerializer, WishlistItemSerializer


class WishlistListView(ListAPIView):
    """List current user's wishlist items (JWT + storefront API key)."""
    serializer_class = WishlistItemSerializer
    permission_classes = [IsStorefrontAPIKey, IsAuthenticated]
    authentication_classes = [JWTAuthenticationAllowAPIKey, SessionAuthentication]
    allow_api_key = True
    access_scope = "storefront"

    def get_queryset(self):
        store = require_api_key_store(self.request)
        return WishlistItem.objects.filter(
            product__store=store,
            user=self.request.user,
        ).select_related('product').prefetch_related('product__images')


class WishlistAddView(APIView):
    """Add product to wishlist. Idempotent."""
    permission_classes = [IsStorefrontAPIKey, IsAuthenticated]
    authentication_classes = [JWTAuthenticationAllowAPIKey, SessionAuthentication]
    allow_api_key = True
    access_scope = "storefront"

    def post(self, request):
        store = require_api_key_store(request)
        ser = WishlistAddSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        product = Product.objects.filter(
            public_id=ser.validated_data['product_public_id'],
            store=store,
            is_active=True,
            status=Product.Status.ACTIVE,
        ).first()
        if not product:
            raise NotFound()
        _, created = WishlistItem.objects.get_or_create(
            product=product,
            user=request.user,
        )
        if created:
            meta_conversions.track_add_to_wishlist(request, product)
        return Response(
            {'status': 'added', 'created': created},
            status=status.HTTP_201_CREATED,
        )


class WishlistRemoveView(APIView):
    """Remove product from wishlist."""
    permission_classes = [IsStorefrontAPIKey, IsAuthenticated]
    authentication_classes = [JWTAuthenticationAllowAPIKey, SessionAuthentication]
    allow_api_key = True
    access_scope = "storefront"

    def post(self, request, product_public_id):
        store = require_api_key_store(request)
        product = Product.objects.filter(
            public_id=product_public_id,
            store=store,
            is_active=True,
            status=Product.Status.ACTIVE,
        ).first()
        if not product:
            raise NotFound()
        deleted, _ = WishlistItem.objects.filter(
            product=product,
            user=request.user,
        ).delete()
        return Response({'status': 'removed', 'deleted': deleted > 0})


class WishlistClearView(APIView):
    """Remove all items from the current user's wishlist."""
    permission_classes = [IsStorefrontAPIKey, IsAuthenticated]
    authentication_classes = [JWTAuthenticationAllowAPIKey, SessionAuthentication]
    allow_api_key = True
    access_scope = "storefront"

    def post(self, request):
        store = require_api_key_store(request)
        deleted, _ = WishlistItem.objects.filter(
            product__store=store,
            user=request.user,
        ).delete()
        return Response({'status': 'cleared', 'deleted': deleted})
