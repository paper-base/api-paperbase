"""Cache-backed read services for storefront review data."""

from __future__ import annotations

from django.conf import settings
from django.db.models import Avg, Count
from rest_framework import serializers

from engine.apps.orders.models import Order, OrderItem
from engine.core.authz import can_override_review
from engine.core import cache_service

from .models import Review
from engine.apps.products.models import Product
from engine.apps.coupons.services import normalize_coupon_email, normalize_phone_digits


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


def _order_access_allowed(*, order: Order, user, phone_proof: str, email_proof: str) -> bool:
    if user is not None and getattr(user, "is_authenticated", False):
        if order.user_id and order.user_id == user.pk:
            return True
    phone_o = normalize_phone_digits(order.phone or "")
    email_o = normalize_coupon_email(order.email or "")
    phone_p = normalize_phone_digits(phone_proof or "")
    email_p = normalize_coupon_email(email_proof or "")
    if phone_p and phone_o and phone_p == phone_o:
        return True
    if email_p and email_o and email_p == email_o:
        return True
    return False


class BaseReviewService:
    """Base boundary for review writes and authorization policy checks."""

    def __init__(self, request):
        self.request = request


class ReviewCreateService(BaseReviewService):
    """Single write pathway for storefront review creation."""

    def create_review(
        self,
        *,
        store,
        user,
        product,
        order_public_id: str,
        rating: int,
        title: str,
        body: str,
        phone_proof: str,
        email_proof: str,
        allow_legacy_binding: bool,
    ) -> Review:
        order_public_id = (order_public_id or "").strip()
        legacy_requested = bool(allow_legacy_binding)
        override_allowed = can_override_review(
            self.request,
            {"allow_legacy_binding_requested": legacy_requested},
        )
        if legacy_requested and not override_allowed:
            raise serializers.ValidationError(
                {"allow_legacy_binding": "Legacy binding override is restricted to internal admin context."}
            )
        if legacy_requested and not bool(
            getattr(settings, "SECURITY_REVIEW_LEGACY_MODE_ENABLED", False)
        ):
            raise serializers.ValidationError(
                {"allow_legacy_binding": "Legacy review binding is currently disabled."}
            )
        if not store:
            raise serializers.ValidationError({"detail": "No active store found."})
        if not product:
            raise serializers.ValidationError({"product": "This field is required."})
        if not order_public_id:
            raise serializers.ValidationError({"order_public_id": "This field is required."})

        order = Order.objects.filter(public_id=order_public_id, store=store).first()
        if not order:
            raise serializers.ValidationError(
                {"detail": "Review requires a valid order in the current store."}
            )

        if not OrderItem.objects.filter(order=order, product=product).exists():
            raise serializers.ValidationError(
                {"detail": "Review requires a matching order line for this product."}
            )
        if Review.objects.filter(order=order, product=product).exists():
            raise serializers.ValidationError(
                {"detail": "A review for this product on this order already exists."}
            )

        if not (override_allowed and legacy_requested):
            if not _order_access_allowed(
                order=order,
                user=user,
                phone_proof=phone_proof,
                email_proof=email_proof,
            ):
                raise serializers.ValidationError(
                    {
                        "detail": (
                            "You must prove access to this order "
                            "(signed-in purchaser or matching phone/email)."
                        )
                    }
                )

        review = Review.objects.create(
            store=store,
            product=product,
            order=order,
            user=user if user and getattr(user, "is_authenticated", False) else None,
            allow_legacy_binding=legacy_requested and override_allowed,
            rating=rating,
            title=title,
            body=body,
            status=Review.Status.PENDING,
        )
        return review
