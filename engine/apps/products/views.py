from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView

from engine.apps.analytics.service import meta_conversions
from engine.core.tenancy import get_active_store, require_resolved_store

from .models import Category, Product, ProductVariant, ProductVariantAttribute
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


class StorefrontTenantMixin:
    """Public storefront: reject platform/anonymous requests with no tenant context."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_resolved_store(request)


class ProductListView(StorefrontTenantMixin, ListAPIView):
    """List products with optional category, brand, and featured filters."""
    serializer_class = ProductListSerializer

    def get_queryset(self):
        ctx = get_active_store(self.request)
        qs = Product.objects.filter(
            store=ctx.store,
            is_active=True,
            status=Product.Status.ACTIVE,
        ).select_related("category").prefetch_related("images").annotate(
            _pub_variant_count=Count("variants", filter=Q(variants__is_active=True)),
            _pub_variant_stock_sum=Sum(
                "variants__stock_quantity", filter=Q(variants__is_active=True)
            ),
        )
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

        return qs.order_by("-created_at", "id")


class ProductDetailView(StorefrontTenantMixin, RetrieveAPIView):
    """Get single product by public_id (prd_xxx) or slug."""
    serializer_class = ProductDetailSerializer
    def get_queryset(self):
        ctx = get_active_store(self.request)
        active_variant_qs = ProductVariant.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                "attribute_values",
                queryset=ProductVariantAttribute.objects.select_related(
                    "attribute_value__attribute"
                ),
            )
        )
        return (
            Product.objects.filter(
                store=ctx.store,
                is_active=True,
                status=Product.Status.ACTIVE,
            )
            .select_related("category")
            .prefetch_related("images", Prefetch("variants", queryset=active_variant_qs))
            .annotate(
                _pub_variant_count=Count("variants", filter=Q(variants__is_active=True)),
                _pub_variant_stock_sum=Sum(
                    "variants__stock_quantity", filter=Q(variants__is_active=True)
                ),
            )
        )
    lookup_url_kwarg = 'identifier'

    def get_object(self):
        # Do NOT accept internal UUID/integer PKs — use public_id or slug only
        identifier = self.kwargs.get(self.lookup_url_kwarg)
        qs = self.get_queryset()
        if identifier and identifier.startswith('prd_'):
            return get_object_or_404(qs, public_id=identifier)
        return get_object_or_404(qs, slug=identifier)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        product = self.get_object()
        meta_conversions.track_view_content(request, product)
        return response


class ProductRelatedView(StorefrontTenantMixin, ListAPIView):
    """Related products for a given product (same category, excluding self)."""
    serializer_class = ProductListSerializer

    def get_queryset(self):
        ctx = get_active_store(self.request)
        identifier = self.kwargs.get('identifier')
        base_qs = Product.objects.filter(
            is_active=True, status=Product.Status.ACTIVE, store=ctx.store
        )
        # Do NOT accept internal UUID/integer PKs — use public_id or slug only
        if identifier and identifier.startswith('prd_'):
            product = get_object_or_404(base_qs, public_id=identifier)
        else:
            product = get_object_or_404(base_qs, slug=identifier)
        return (
            Product.objects.filter(
                is_active=True,
                status=Product.Status.ACTIVE,
                store=ctx.store,
                category=product.category,
            )
            .exclude(id=product.id)
            .select_related("category")
            .prefetch_related("images")
            .annotate(
                _pub_variant_count=Count("variants", filter=Q(variants__is_active=True)),
                _pub_variant_stock_sum=Sum(
                    "variants__stock_quantity", filter=Q(variants__is_active=True)
                ),
            )
            .order_by("-created_at", "id")[:4]
        )


class CategoryListView(StorefrontTenantMixin, ListAPIView):
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


class CategoryDetailView(StorefrontTenantMixin, RetrieveAPIView):
    """Get a single subcategory by slug."""
    serializer_class = CategorySerializer
    lookup_field = 'slug'

    def get_queryset(self):
        ctx = get_active_store(self.request)
        return Category.objects.filter(
            store=ctx.store,
            is_active=True,
        )


class ProductSearchView(StorefrontTenantMixin, ListAPIView):
    """
    Real-time product search endpoint.
    Searches product name, brand, and description fields.
    """
    serializer_class = ProductListSerializer

    def get_queryset(self):
        ctx = get_active_store(self.request)
        query = self.request.query_params.get('q', '').strip()

        if not query or len(query) < 2:
            return Product.objects.none()

        qs = (
            Product.objects.filter(
                is_active=True, status=Product.Status.ACTIVE, store=ctx.store
            )
            .select_related('category')
            .prefetch_related('images')
        )

        qs = qs.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(description__icontains=query)
        )

        return qs.order_by('name', 'id')[:10]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        query = request.query_params.get('q', '').strip()
        if query and len(query) >= 2:
            meta_conversions.track_search(request, query)
        return response
