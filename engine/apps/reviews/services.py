"""Cache-backed read services for storefront review data."""

from __future__ import annotations

from django.conf import settings
from django.db.models import Avg, Count

from engine.core import cache_service

from .models import Review
from .serializers import ReviewSerializer
from engine.apps.products.models import Product


# ---------------------------------------------------------------------------
# Review list (paginated — view handles pagination, service handles cache)
# ---------------------------------------------------------------------------

def _review_list_key(store_public_id: str, params: dict) -> str:
    return cache_service.build_key(
        store_public_id, "reviews", f"list:{cache_service.hash_params(params)}"
    )


def _normalize_review_params(query_params) -> dict:
    return {
        "page": query_params.get("page", "1"),
        "product_public_id": query_params.get("product_public_id", ""),
    }


def get_cached_review_list(store_public_id: str, query_params):
    """Return cached paginated review list data, or ``None`` on miss."""
    params = _normalize_review_params(query_params)
    return cache_service.get(_review_list_key(store_public_id, params))


def set_cached_review_list(store_public_id: str, query_params, data) -> None:
    params = _normalize_review_params(query_params)
    cache_service.set(
        _review_list_key(store_public_id, params),
        data,
        settings.CACHE_TTL_REVIEWS,
    )


def build_review_list_queryset(store, query_params):
    """Build filtered review queryset for the storefront."""
    product_public_id = query_params.get("product_public_id")
    if not product_public_id:
        return Review.objects.none()
    return (
        Review.objects.filter(
            product__public_id=product_public_id,
            product__store=store,
            status=Review.Status.APPROVED,
        )
        .select_related("user")
        .order_by("-created_at")
    )


# ---------------------------------------------------------------------------
# Review summary (single aggregation — fully handled by service)
# ---------------------------------------------------------------------------

def get_review_summary(store, product_public_id: str):
    """Return cached review summary ``{average_rating, count}`` for a product."""
    if not product_public_id:
        return {"average_rating": None, "count": 0}

    key = cache_service.build_key(
        store.public_id, "review_summary", product_public_id
    )

    def fetcher():
        product_exists = Product.objects.filter(
            public_id=product_public_id,
            store=store,
            is_active=True,
            status=Product.Status.ACTIVE,
        ).exists()
        if not product_exists:
            return None
        agg = Review.objects.filter(
            product__public_id=product_public_id,
            product__store=store,
            status=Review.Status.APPROVED,
        ).aggregate(avg=Avg("rating"), count=Count("id"))
        return {
            "average_rating": (
                round(agg["avg"], 2) if agg["avg"] is not None else None
            ),
            "count": agg["count"] or 0,
        }

    return cache_service.get_or_set(key, fetcher, settings.CACHE_TTL_REVIEW_SUMMARY)


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------

def invalidate_review_cache(store_public_id: str, product_public_id: str = "") -> None:
    """Clear review caches for a store, optionally scoped to a product."""
    cache_service.invalidate_store_resource(store_public_id, "reviews")
    if product_public_id:
        cache_service.delete(
            cache_service.build_key(
                store_public_id, "review_summary", product_public_id
            )
        )
    else:
        cache_service.invalidate_store_resource(store_public_id, "review_summary")
