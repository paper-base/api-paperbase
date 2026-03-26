"""
Cache-backed read services for storefront product and category data.

All cache keys are tenant-scoped via store public_id.
Query construction logic lives here so views remain thin request/response handlers.
"""

from __future__ import annotations

from django.conf import settings
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404

from engine.core import cache_service

from .models import Category, Product, ProductVariant, ProductVariantAttribute
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


# ---------------------------------------------------------------------------
# Product list (paginated — view handles pagination, service handles cache)
# ---------------------------------------------------------------------------

def _product_list_key(store_public_id: str, params: dict) -> str:
    return cache_service.build_key(
        store_public_id, "products", f"list:{cache_service.hash_params(params)}"
    )


def _normalize_list_params(query_params) -> dict:
    return {
        "page": query_params.get("page", "1"),
        "category": query_params.get("category", ""),
        "brand": query_params.get("brand", ""),
        "featured": query_params.get("featured", ""),
        "hot_deals": query_params.get("hot_deals", ""),
    }


def get_cached_product_list(store_public_id: str, query_params):
    """Return cached paginated product list data, or ``None`` on miss."""
    params = _normalize_list_params(query_params)
    return cache_service.get(_product_list_key(store_public_id, params))


def set_cached_product_list(store_public_id: str, query_params, data) -> None:
    """Store paginated product list response in cache."""
    params = _normalize_list_params(query_params)
    cache_service.set(
        _product_list_key(store_public_id, params),
        data,
        settings.CACHE_TTL_PRODUCT_LIST,
    )


def build_product_list_queryset(store, query_params):
    """Build the filtered, annotated product queryset for the storefront list."""
    qs = (
        Product.objects.filter(
            store=store,
            is_active=True,
            status=Product.Status.ACTIVE,
        )
        .select_related("category")
        .prefetch_related("images")
        .annotate(
            _pub_variant_count=Count("variants", filter=Q(variants__is_active=True)),
            _pub_variant_stock_sum=Sum(
                "variants__stock_quantity", filter=Q(variants__is_active=True)
            ),
        )
    )

    category = query_params.get("category")
    if category:
        slugs = [c.strip() for c in category.split(",") if c.strip()]
        if slugs:
            qs = qs.filter(category__slug__in=slugs)

    brand = query_params.get("brand")
    if brand:
        brands = [b.strip() for b in brand.split(",") if b.strip()]
        if brands:
            qs = qs.filter(brand__in=brands)

    featured = query_params.get("featured")
    if featured and featured.lower() == "true":
        qs = qs.filter(is_featured=True)

    hot_deals = query_params.get("hot_deals")
    if hot_deals and hot_deals.lower() == "true":
        qs = qs.filter(badge="sale")

    return qs.order_by("-created_at", "id")


# ---------------------------------------------------------------------------
# Product detail (single object — fully handled by service)
# ---------------------------------------------------------------------------

def get_product_detail(store, identifier: str, request):
    """Return cached product detail data, falling back to DB on miss."""
    key = cache_service.build_key(store.public_id, "product", identifier)

    def fetcher():
        active_variant_qs = ProductVariant.objects.filter(
            is_active=True
        ).prefetch_related(
            Prefetch(
                "attribute_values",
                queryset=ProductVariantAttribute.objects.select_related(
                    "attribute_value__attribute"
                ),
            )
        )
        qs = (
            Product.objects.filter(
                store=store,
                is_active=True,
                status=Product.Status.ACTIVE,
            )
            .select_related("category")
            .prefetch_related(
                "images", Prefetch("variants", queryset=active_variant_qs)
            )
            .annotate(
                _pub_variant_count=Count(
                    "variants", filter=Q(variants__is_active=True)
                ),
                _pub_variant_stock_sum=Sum(
                    "variants__stock_quantity",
                    filter=Q(variants__is_active=True),
                ),
            )
        )
        if identifier.startswith("prd_"):
            product = get_object_or_404(qs, public_id=identifier)
        else:
            product = get_object_or_404(qs, slug=identifier)
        return ProductDetailSerializer(
            product, context={"request": request}
        ).data

    return cache_service.get_or_set(key, fetcher, settings.CACHE_TTL_PRODUCT_DETAIL)


# ---------------------------------------------------------------------------
# Related products (small list, max 4 — fully handled by service)
# ---------------------------------------------------------------------------

def get_related_products(store, identifier: str, request):
    """Return cached related-products list, falling back to DB on miss."""
    key = cache_service.build_key(store.public_id, "related", identifier)

    def fetcher():
        base_qs = Product.objects.filter(
            is_active=True, status=Product.Status.ACTIVE, store=store
        )
        if identifier.startswith("prd_"):
            product = get_object_or_404(base_qs, public_id=identifier)
        else:
            product = get_object_or_404(base_qs, slug=identifier)
        qs = (
            Product.objects.filter(
                is_active=True,
                status=Product.Status.ACTIVE,
                store=store,
                category=product.category,
            )
            .exclude(id=product.id)
            .select_related("category")
            .prefetch_related("images")
            .annotate(
                _pub_variant_count=Count(
                    "variants", filter=Q(variants__is_active=True)
                ),
                _pub_variant_stock_sum=Sum(
                    "variants__stock_quantity",
                    filter=Q(variants__is_active=True),
                ),
            )
            .order_by("-created_at", "id")[:4]
        )
        return ProductListSerializer(
            qs, many=True, context={"request": request}
        ).data

    return cache_service.get_or_set(key, fetcher, settings.CACHE_TTL_RELATED_PRODUCTS)


# ---------------------------------------------------------------------------
# Category list (paginated)
# ---------------------------------------------------------------------------

def _category_list_key(store_public_id: str, params: dict) -> str:
    return cache_service.build_key(
        store_public_id, "categories", f"list:{cache_service.hash_params(params)}"
    )


def _normalize_category_params(query_params) -> dict:
    return {
        "page": query_params.get("page", "1"),
        "parent": query_params.get("parent", ""),
    }


def get_cached_category_list(store_public_id: str, query_params):
    """Return cached paginated category list data, or ``None`` on miss."""
    params = _normalize_category_params(query_params)
    return cache_service.get(_category_list_key(store_public_id, params))


def set_cached_category_list(store_public_id: str, query_params, data) -> None:
    params = _normalize_category_params(query_params)
    cache_service.set(
        _category_list_key(store_public_id, params),
        data,
        settings.CACHE_TTL_CATEGORIES,
    )


def build_category_list_queryset(store, query_params):
    """Build filtered category queryset for the storefront list."""
    qs = Category.objects.filter(store=store, is_active=True)
    parent_slug = query_params.get("parent")
    if parent_slug:
        parent = get_object_or_404(
            Category.objects.filter(store=store, is_active=True),
            slug=parent_slug,
        )
        qs = qs.filter(parent=parent)
    else:
        qs = qs.filter(parent__isnull=True)
    return qs


# ---------------------------------------------------------------------------
# Category detail (single object)
# ---------------------------------------------------------------------------

def get_category_detail(store, slug: str, request):
    """Return cached category detail data, falling back to DB on miss."""
    key = cache_service.build_key(store.public_id, "category", slug)

    def fetcher():
        obj = get_object_or_404(
            Category.objects.filter(store=store, is_active=True), slug=slug
        )
        return CategorySerializer(obj, context={"request": request}).data

    return cache_service.get_or_set(key, fetcher, settings.CACHE_TTL_CATEGORIES)


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

def invalidate_product_cache(store_public_id: str) -> None:
    """Clear all product-related caches for a store."""
    cache_service.invalidate_store_resource(store_public_id, "products")
    cache_service.invalidate_store_resource(store_public_id, "product")
    cache_service.invalidate_store_resource(store_public_id, "related")


def invalidate_category_cache(store_public_id: str) -> None:
    """Clear all category caches for a store (also affects product list)."""
    cache_service.invalidate_store_resource(store_public_id, "categories")
    cache_service.invalidate_store_resource(store_public_id, "category")
    cache_service.invalidate_store_resource(store_public_id, "products")
