"""Derived subscription calendar state (not stored in DB)."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.utils import timezone

from engine.utils.time import BD_TZ, bd_calendar_date

from .models import Subscription

logger = logging.getLogger(__name__)


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

    1) If a DB ACTIVE row exists, a newer PENDING_REVIEW or REJECTED row can override **only
       while the active row is still calendar ACTIVE or GRACE**. Once the paid period is
       past grace (calendar EXPIRED), keep the ACTIVE row so the UI shows renew/expired,
       not a stale rejected renewal attempt.
    2) No ACTIVE → latest PENDING_REVIEW (if any).
    3) Else: a DB **EXPIRED** subscription row (lapsed paid period) wins over **REJECTED**
       for messaging. Otherwise compare non-rejected vs REJECTED by ``updated_at``.
    """
    active = (
        Subscription.objects.filter(user=user, status=Subscription.Status.ACTIVE)
        .select_related("plan")
        .order_by("-end_date")
        .first()
    )
    pending = (
        Subscription.objects.filter(user=user, status=Subscription.Status.PENDING_REVIEW)
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    rejected = (
        Subscription.objects.filter(user=user, status=Subscription.Status.REJECTED)
        .select_related("plan")
        .order_by("-updated_at", "-created_at")
        .first()
    )

    if active:
        cal = get_subscription_status(active)
        if cal in ("ACTIVE", "GRACE"):
            newer = [
                s
                for s in (pending, rejected)
                if s is not None and s.updated_at > active.updated_at
            ]
            if newer:
                return max(newer, key=lambda s: s.updated_at)
        return active

    if pending:
        return pending
    non_rejected = (
        Subscription.objects.filter(user=user)
        .exclude(status=Subscription.Status.CANCELED)
        .exclude(status=Subscription.Status.REJECTED)
        .select_related("plan")
        .order_by("-end_date")
        .first()
    )
    if non_rejected and non_rejected.status == Subscription.Status.EXPIRED:
        return non_rejected
    if rejected and non_rejected:
        if rejected.updated_at > non_rejected.updated_at:
            return rejected
        return non_rejected
    if non_rejected:
        return non_rejected
    return rejected


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

STORE_INACTIVE_DETAIL = {
    "error": "STORE_INACTIVE",
    "message": "Store is unavailable.",
}


def assert_storefront_subscription_allows_for_owner(owner) -> None:
    """
    Central check for customer-facing (API key) traffic: raise PermissionDenied
    when the owner's subscription does not allow a live storefront.

    When ``get_user_subscription_status`` is PENDING_REVIEW or REJECTED because a
    newer renewal row overrides the candidate, storefront access still applies if
    any DB ACTIVE row remains in calendar ACTIVE or GRACE (paid period not lapsed).
    """
    from rest_framework.exceptions import PermissionDenied

    if owner is None:
        return
    uss = get_user_subscription_status(owner)
    if uss == "NONE":
        raise PermissionDenied(detail=STORE_INACTIVE_DETAIL)
    if uss == "EXPIRED":
        raise PermissionDenied(detail=SUBSCRIPTION_EXPIRED_DETAIL)
    if uss in ("PENDING_REVIEW", "REJECTED"):
        active_sub = (
            Subscription.objects.filter(user=owner, status=Subscription.Status.ACTIVE)
            .order_by("-end_date")
            .first()
        )
        if active_sub is not None:
            cal_status = get_subscription_status(active_sub)
            if cal_status in ("ACTIVE", "GRACE"):
                logger.info(
                    "Bypassed PENDING_REVIEW block due to active/grace subscription"
                )
                return
        raise PermissionDenied(detail=STOREFRONT_UNAVAILABLE_DETAIL)


def dashboard_subscription_access_ok(user) -> bool:
    """
    Dashboard JWT access: NONE/REJECTED/EXPIRED → allow (manage store, renew);
    PENDING_REVIEW → allow; ACTIVE/GRACE → calendar-paid period required.
    Storefront gating uses assert_storefront_subscription_allows_for_owner.
    """
    uss = get_user_subscription_status(user)
    if uss in ("NONE", "REJECTED", "PENDING_REVIEW", "EXPIRED"):
        return True
    return get_subscription_for_api_access(user) is not None
