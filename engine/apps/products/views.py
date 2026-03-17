from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from engine.apps.analytics.service import meta_conversions
from engine.core.tenancy import get_active_store

from .models import Brand, Category, Product
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


class ProductListView(ListAPIView):
    """List products with optional category, subcategory, brand, and featured filters."""
    serializer_class = ProductListSerializer

    def get_queryset(self):
        ctx = get_active_store(self.request)
        qs = Product.objects.filter(
            store=ctx.store,
            is_active=True,
            status=Product.Status.ACTIVE,
        ).select_related("category").prefetch_related("images")
        category = self.request.query_params.get('category')
        brand = self.request.query_params.get('brand')

        if category:
            # Support comma-separated category slugs
            category_slugs = [c.strip() for c in category.split(',') if c.strip()]
            if category_slugs:
                qs = qs.filter(category__slug__in=category_slugs)

        if brand:
            brands = [b.strip() for b in brand.split(',') if b.strip()]
            if brands:
                qs = qs.filter(brand__in=brands)

        featured = self.request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            qs = qs.filter(is_featured=True)

        hot_deals = self.request.query_params.get('hot_deals')
        if hot_deals and hot_deals.lower() == 'true':
            qs = qs.filter(badge='sale')

        return qs


class ProductDetailView(RetrieveAPIView):
    """Get single product by UUID or slug."""
    serializer_class = ProductDetailSerializer
    def get_queryset(self):
        ctx = get_active_store(self.request)
        return Product.objects.filter(
            store=ctx.store,
            is_active=True,
            status=Product.Status.ACTIVE,
        ).select_related("category").prefetch_related("images")
    lookup_url_kwarg = 'identifier'

    def get_object(self):
        identifier = self.kwargs.get(self.lookup_url_kwarg)
        qs = self.get_queryset()
        try:
            import uuid

            uuid.UUID(str(identifier))
            return get_object_or_404(qs, id=identifier)
        except Exception:
            return get_object_or_404(qs, slug=identifier)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        product = self.get_object()
        meta_conversions.track_view_content(request, product)
        return response


class ProductRelatedView(ListAPIView):
    """Related products for a given product (same category, excluding self)."""
    serializer_class = ProductListSerializer

    def get_queryset(self):
        identifier = self.kwargs.get('identifier')
        qs = Product.objects.filter(is_active=True, status=Product.Status.ACTIVE)
        try:
            import uuid

            uuid.UUID(str(identifier))
            product = get_object_or_404(qs, id=identifier)
        except Exception:
            product = get_object_or_404(qs, slug=identifier)
        return (
            Product.objects.filter(is_active=True, status=Product.Status.ACTIVE, category=product.category)
            .exclude(id=product.id)
            .select_related('category')
            .prefetch_related('images')[:4]
        )


class CategoryListView(ListAPIView):
    """List categories, optionally filtered by parent slug."""
    serializer_class = CategorySerializer

    def get_queryset(self):
        ctx = get_active_store(self.request)
        qs = Category.objects.filter(
            store=ctx.store,
            is_active=True,
        )
        parent_slug = self.request.query_params.get('parent')
        if parent_slug:
            parent = get_object_or_404(
                Category.objects.filter(store=ctx.store, is_active=True),
                slug=parent_slug,
            )
            qs = qs.filter(parent=parent)
        else:
            qs = qs.filter(parent__isnull=True)
        return qs


class CategoryDetailView(RetrieveAPIView):
    """Get a single subcategory by slug."""
    serializer_class = CategorySerializer
    lookup_field = 'slug'

    def get_queryset(self):
        ctx = get_active_store(self.request)
        return Category.objects.filter(
            store=ctx.store,
            is_active=True,
        )


class BrandListView(APIView):
    """
    List all unique product brands, optionally filtered by navbar category.
    Returns brand names sorted alphabetically.
    """
    def get(self, request):
        category_slug = request.query_params.get('category')

        qs = Product.objects.filter(is_active=True, status=Product.Status.ACTIVE)

        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        brands = qs.values_list('brand', flat=True).distinct().order_by('brand')

        return Response(list(brands))


class BrandShowcaseView(APIView):
    """
    List all active brands for the homepage showcase.
    Can filter by brand_type (accessories, gadgets) using query parameter.
    """
    def get(self, request):
        brand_type = request.query_params.get('type')

        qs = Brand.objects.filter(is_active=True)

        if brand_type:
            qs = qs.filter(brand_type=brand_type)

        serializer = BrandSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class ProductSearchView(ListAPIView):
    """
    Real-time product search endpoint.
    Searches product name, brand, and description fields.
    """
    serializer_class = ProductListSerializer

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()

        if not query or len(query) < 2:
            return Product.objects.none()

        qs = (
            Product.objects.filter(is_active=True, status=Product.Status.ACTIVE)
            .select_related('category')
            .prefetch_related('images')
        )

        qs = qs.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(description__icontains=query)
        )

        return qs.order_by('name')[:10]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        query = request.query_params.get('q', '').strip()
        if query and len(query) >= 2:
            meta_conversions.track_search(request, query)
        return response
