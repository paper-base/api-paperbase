"""Derived subscription calendar state (not stored in DB)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.utils import timezone

from engine.utils.time import BD_TZ, bd_calendar_date

from .models import Subscription


def get_subscription_status(subscription: Subscription) -> str:
    """
    Return PENDING_REVIEW, REJECTED, ACTIVE, GRACE, or EXPIRED.

    DB statuses pending_review / rejected short-circuit before calendar logic.
    Uses timezone.now() via bd_calendar_date for comparison with end_date.
    DB status EXPIRED wins immediately (no grace).
    """
    if subscription.status == Subscription.Status.PENDING_REVIEW:
        return "PENDING_REVIEW"
    if subscription.status == Subscription.Status.REJECTED:
        return "REJECTED"
    if subscription.status == Subscription.Status.EXPIRED:
        return "EXPIRED"
    today = bd_calendar_date(timezone.now())
    end = subscription.end_date
    if today <= end:
        return "ACTIVE"
    if today == end + timedelta(days=1):
        return "GRACE"
    return "EXPIRED"


def storefront_blocks_at(subscription: Subscription) -> datetime:
    """
    First instant storefront APIs block for this subscription: start of Asia/Dhaka
    calendar day (end_date + 2 days). After end_date is ACTIVE; end_date+1 is GRACE;
    from end_date+2 onward the owner is EXPIRED for storefront (see IsStorefrontAPIKey).
    """
    block_date = subscription.end_date + timedelta(days=2)
    return datetime.combine(block_date, time.min, tzinfo=BD_TZ)


def get_candidate_subscription_row(user) -> Subscription | None:
    """
    Row used for status and feature access.

    Precedence:
    1) DB ACTIVE — calendar-derived ACTIVE/GRACE/EXPIRED for paid period.
    2) PENDING_REVIEW — payment submitted, awaiting admin approval.
    3) Latest non-canceled row (e.g. EXPIRED, REJECTED) by end_date.
    """
    sub = (
        Subscription.objects.filter(user=user, status=Subscription.Status.ACTIVE)
        .select_related("plan")
        .order_by("-end_date")
        .first()
    )
    if sub:
        return sub
    pending = (
        Subscription.objects.filter(user=user, status=Subscription.Status.PENDING_REVIEW)
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    if pending:
        return pending
    return (
        Subscription.objects.filter(user=user)
        .exclude(status=Subscription.Status.CANCELED)
        .select_related("plan")
        .order_by("-end_date")
        .first()
    )


def get_user_subscription_status(user) -> str:
    """NONE, PENDING_REVIEW, REJECTED, ACTIVE, GRACE, or EXPIRED."""
    sub = get_candidate_subscription_row(user)
    if not sub:
        return "NONE"
    return get_subscription_status(sub)


def get_subscription_for_api_access(user) -> Subscription | None:
    """Subscription row when API access is allowed (ACTIVE or GRACE); None if NONE or EXPIRED."""
    sub = get_candidate_subscription_row(user)
    if not sub:
        return None
    st = get_subscription_status(sub)
    if st in ("ACTIVE", "GRACE"):
        return sub
    return None


SUBSCRIPTION_EXPIRED_DETAIL = {
    "error": "subscription_expired",
    "message": (
        "Your subscription has expired. Please renew your plan to regain full access."
    ),
}

STOREFRONT_UNAVAILABLE_DETAIL = {
    "error": "storefront_unavailable",
    "message": (
        "The storefront is not available yet. Please complete setup or wait for approval."
    ),
}


def dashboard_subscription_access_ok(user) -> bool:
    """
    Dashboard JWT access: NONE/REJECTED → deny; PENDING_REVIEW → allow;
    EXPIRED → allow (read UI, renew); ACTIVE/GRACE → need paid row.
    Storefront uses IsStorefrontAPIKey + owner checks instead.
    """
    uss = get_user_subscription_status(user)
    if uss in ("NONE", "REJECTED"):
        return False
    if uss == "PENDING_REVIEW":
        return True
    if uss == "EXPIRED":
        return True
    return get_subscription_for_api_access(user) is not None
