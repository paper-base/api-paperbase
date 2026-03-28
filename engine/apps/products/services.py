"""
Cache-backed read services for storefront product and category data.

All cache keys are tenant-scoped via store public_id.
Query construction logic lives here so views remain thin request/response handlers.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Count, Max, Min, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404

from engine.core import cache_service

from .models import (
    Category,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttribute,
)
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
from .stock_signals import get_low_stock_threshold


# ---------------------------------------------------------------------------
# Product list (paginated — view handles pagination, service handles cache)
# ---------------------------------------------------------------------------

def _product_list_key(store_public_id: str, params: dict) -> str:
    return cache_service.build_key(
        store_public_id, "products", f"list:{cache_service.hash_params(params)}"
    )


def _normalize_list_params(query_params) -> dict:
    ordering = (query_params.get("ordering") or "").strip()
    if not ordering:
        ordering = (query_params.get("sort") or "").strip() or "newest"
    return {
        "page": query_params.get("page", "1"),
        "category": query_params.get("category", ""),
        "brand": query_params.get("brand", ""),
        "search": query_params.get("search", ""),
        "price_min": query_params.get("price_min", ""),
        "price_max": query_params.get("price_max", ""),
        "attributes": query_params.get("attributes", ""),
        "ordering": ordering,
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
                "variants__inventory__quantity", filter=Q(variants__is_active=True)
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

    search = (query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(brand__icontains=search)
        )

    try:
        if "price_min" in query_params:
            price_min_raw = (query_params.get("price_min") or "").strip()
            if price_min_raw:
                qs = qs.filter(price__gte=Decimal(price_min_raw))
        if "price_max" in query_params:
            price_max_raw = (query_params.get("price_max") or "").strip()
            if price_max_raw:
                qs = qs.filter(price__lte=Decimal(price_max_raw))
    except (InvalidOperation, ValueError):
        pass

    attributes = (query_params.get("attributes") or "").strip()
    if attributes:
        attr_value_ids = [v.strip() for v in attributes.split(",") if v.strip()]
        if attr_value_ids:
            qs = qs.filter(
                variants__is_active=True,
                variants__attribute_values__attribute_value__public_id__in=attr_value_ids,
            ).distinct()

    featured = query_params.get("featured")
    if featured and featured.lower() == "true":
        qs = qs.filter(is_featured=True)

    hot_deals = query_params.get("hot_deals")
    if hot_deals and hot_deals.lower() == "true":
        qs = qs.filter(badge="sale")

    ordering = (query_params.get("ordering") or "").strip().lower()
    if not ordering:
        ordering = (query_params.get("sort") or "").strip().lower() or "newest"
    if ordering == "price_asc":
        return qs.order_by("price", "id")
    if ordering == "price_desc":
        return qs.order_by("-price", "id")
    if ordering == "popularity":
        return qs.annotate(_order_count=Count("orderitem")).order_by("-_order_count", "-created_at", "id")
    return qs.order_by("-created_at", "id")


# ---------------------------------------------------------------------------
# Related products (shared query for detail + /related/)
# ---------------------------------------------------------------------------


def _serialize_related_products(store, product, request):
    threshold = get_low_stock_threshold(store)
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
                "variants__inventory__quantity",
                filter=Q(variants__is_active=True),
            ),
        )
        .order_by("-created_at", "id")[:4]
    )
    return ProductListSerializer(
        qs,
        many=True,
        context={"request": request, "low_stock_threshold": threshold},
    ).data


def _variant_matrix_for_product(product) -> dict[str, list[dict[str, str]]]:
    matrix: dict[str, list[dict[str, str]]] = {}
    seen: dict[str, set[str]] = {}
    for variant in product.variants.all():
        if not variant.is_active:
            continue
        for link in variant.attribute_values.all():
            av = link.attribute_value
            slug = av.attribute.slug
            if slug not in seen:
                seen[slug] = set()
                matrix[slug] = []
            pid = av.public_id
            if pid in seen[slug]:
                continue
            seen[slug].add(pid)
            matrix[slug].append({"value": av.value, "id": pid})
    return matrix


def _category_breadcrumb_names(product) -> list[str]:
    names: list[str] = []
    cat = product.category
    while cat is not None:
        names.append(cat.name)
        cat = cat.parent
    return list(reversed(names))


# ---------------------------------------------------------------------------
# Product detail (single object — fully handled by service)
# ---------------------------------------------------------------------------

def get_product_detail(store, identifier: str, request):
    """Return cached product detail data, falling back to DB on miss."""
    key = cache_service.build_key(store.public_id, "product", identifier)

    def fetcher():
        active_variant_qs = ProductVariant.objects.filter(
            is_active=True
        ).select_related("inventory").prefetch_related(
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
                    "variants__inventory__quantity",
                    filter=Q(variants__is_active=True),
                ),
            )
        )
        if identifier.startswith("prd_"):
            product = get_object_or_404(qs, public_id=identifier)
        else:
            product = get_object_or_404(qs, slug=identifier)
        threshold = get_low_stock_threshold(store)
        data = ProductDetailSerializer(
            product,
            context={
                "request": request,
                "low_stock_threshold": threshold,
            },
        ).data
        data["breadcrumbs"] = ["Home"] + _category_breadcrumb_names(product) + [
            product.name
        ]
        data["related_products"] = _serialize_related_products(
            store, product, request
        )
        data["variant_matrix"] = _variant_matrix_for_product(product)
        return data

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
        return _serialize_related_products(store, product, request)

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
    cache_service.invalidate_store_resource(store_public_id, "catalog")


def invalidate_category_cache(store_public_id: str) -> None:
    """Clear all category caches for a store (also affects product list)."""
    cache_service.invalidate_store_resource(store_public_id, "categories")
    cache_service.invalidate_store_resource(store_public_id, "category")
    cache_service.invalidate_store_resource(store_public_id, "products")
    cache_service.invalidate_store_resource(store_public_id, "catalog")


# ---------------------------------------------------------------------------
# Catalog filter metadata (storefront sidebar / filter UI)
# ---------------------------------------------------------------------------


def _fetch_catalog_filters_payload(store) -> dict:
    """Build filter metadata for active storefront products (uncached)."""
    base_p = Product.objects.filter(
        store=store,
        is_active=True,
        status=Product.Status.ACTIVE,
    )
    cat_ids = base_p.values_list("category_id", flat=True).distinct()
    categories = (
        Category.objects.filter(store=store, is_active=True, id__in=cat_ids)
        .order_by("order", "name")
        .only("public_id", "name")
    )
    categories_data = [{"id": c.public_id, "name": c.name} for c in categories]

    brands = list(
        base_p.exclude(brand__isnull=True)
        .exclude(brand="")
        .values_list("brand", flat=True)
        .distinct()
        .order_by("brand")
    )

    agg = base_p.aggregate(mn=Min("price"), mx=Max("price"))
    mn, mx = agg["mn"], agg["mx"]
    price_range = {
        "min": float(mn) if mn is not None else 0.0,
        "max": float(mx) if mx is not None else 0.0,
    }

    attr_ids_in_use = (
        ProductAttributeValue.objects.filter(
            store=store,
            variant_links__variant__is_active=True,
            variant_links__variant__product__store=store,
            variant_links__variant__product__is_active=True,
            variant_links__variant__product__status=Product.Status.ACTIVE,
        )
        .values_list("attribute_id", flat=True)
        .distinct()
    )
    attributes_out: dict[str, list[dict[str, str]]] = {}
    for attr in (
        ProductAttribute.objects.filter(store=store, id__in=attr_ids_in_use)
        .order_by("order", "name")
        .only("slug", "id")
    ):
        values = (
            ProductAttributeValue.objects.filter(
                attribute=attr,
                store=store,
                variant_links__variant__is_active=True,
                variant_links__variant__product__store=store,
                variant_links__variant__product__is_active=True,
                variant_links__variant__product__status=Product.Status.ACTIVE,
            )
            .order_by("order", "value")
            .distinct()
        )
        seen: set[str] = set()
        rows: list[dict[str, str]] = []
        for v in values:
            if v.public_id in seen:
                continue
            seen.add(v.public_id)
            rows.append({"id": v.public_id, "value": v.value})
        if rows:
            attributes_out[attr.slug] = rows

    return {
        "categories": categories_data,
        "attributes": attributes_out,
        "brands": brands,
        "price_range": price_range,
    }


def get_catalog_filters(store) -> dict:
    """Cached catalog filter metadata for the storefront."""
    key = cache_service.build_key(store.public_id, "catalog", "filters")

    def fetcher():
        return _fetch_catalog_filters_payload(store)

    return cache_service.get_or_set(
        key, fetcher, settings.CACHE_TTL_CATALOG_FILTERS
    )
