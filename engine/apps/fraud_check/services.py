from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from engine.apps.stores.models import Store
from engine.core.tenant_execution import system_scope

from .models import FraudCheckLog

logger = logging.getLogger(__name__)


FRAUD_CHECK_URL = "https://api.bdcourier.com/courier-check"


def _normalize_phone_strict(phone: str) -> str:
    raw = (phone or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) != 11:
        raise ValidationError({"phone": "Phone number must be exactly 11 digits."})
    if not digits.startswith("01"):
        raise ValidationError({"phone": 'Phone number must start with "01".'})
    return digits


def _date_range_for_day(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _date_range_for_month(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _ttl_cutoff(now: datetime) -> datetime:
    ttl_days = int(getattr(settings, "FRAUD_CACHE_TTL_DAYS", 3) or 0)
    if ttl_days <= 0:
        ttl_days = 1
    return now - timedelta(days=ttl_days)


def _limit_value(name: str) -> int:
    value = int(getattr(settings, name, 0) or 0)
    return max(0, value)


@dataclass(frozen=True)
class FraudCheckResult:
    cached: bool
    status: str
    response_json: dict[str, Any]
    log_id: int | None = None
    limit_exceeded: str | None = None


def _latest_cached_log(*, store: Store, normalized_phone: str, cutoff: datetime) -> FraudCheckLog | None:
    return (
        FraudCheckLog.objects.filter(store=store, normalized_phone=normalized_phone, checked_at__gte=cutoff)
        .order_by("-checked_at", "-id")
        .first()
    )


def _counts_for_limits(*, store: Store, now: datetime) -> dict[str, int]:
    day_start, day_end = _date_range_for_day(now)
    month_start, month_end = _date_range_for_month(now)

    store_daily = FraudCheckLog.objects.filter(store=store, checked_at__gte=day_start, checked_at__lt=day_end).count()
    store_monthly = FraudCheckLog.objects.filter(
        store=store, checked_at__gte=month_start, checked_at__lt=month_end
    ).count()

    with system_scope(reason="fraud_check_global_limits"):
        global_daily = FraudCheckLog.objects.filter(checked_at__gte=day_start, checked_at__lt=day_end).count()
        global_monthly = FraudCheckLog.objects.filter(
            checked_at__gte=month_start, checked_at__lt=month_end
        ).count()

    return {
        "store_daily": int(store_daily),
        "store_monthly": int(store_monthly),
        "global_daily": int(global_daily),
        "global_monthly": int(global_monthly),
    }


def _check_limits(*, counts: dict[str, int]) -> str | None:
    store_daily_limit = _limit_value("STORE_DAILY_LIMIT")
    store_monthly_limit = _limit_value("STORE_MONTHLY_LIMIT")
    global_daily_limit = _limit_value("GLOBAL_DAILY_LIMIT")
    global_monthly_limit = _limit_value("GLOBAL_MONTHLY_LIMIT")

    if store_daily_limit and counts["store_daily"] >= store_daily_limit:
        return "store_daily"
    if store_monthly_limit and counts["store_monthly"] >= store_monthly_limit:
        return "store_monthly"
    if global_daily_limit and counts["global_daily"] >= global_daily_limit:
        return "global_daily"
    if global_monthly_limit and counts["global_monthly"] >= global_monthly_limit:
        return "global_monthly"
    return None


def _lock_key(store: Store, normalized_phone: str) -> str:
    return f"lock:fraud_check:{store.public_id}:{normalized_phone}"


def _acquire_lock(*, store: Store, normalized_phone: str) -> bool:
    key = _lock_key(store, normalized_phone)
    try:
        return bool(cache.add(key, "1", timeout=30))
    except Exception:
        logger.warning("fraud_check lock cache.add failed", exc_info=True)
        return True


def _release_lock(*, store: Store, normalized_phone: str) -> None:
    key = _lock_key(store, normalized_phone)
    try:
        cache.delete(key)
    except Exception:
        logger.warning("fraud_check lock cache.delete failed", exc_info=True)


def run_fraud_check(*, store: Store, phone: str) -> FraudCheckResult:
    """
    DB-first cache, API-second courier fraud check.
    All data is strictly scoped by store_id.
    """
    now = timezone.now()
    normalized_phone = _normalize_phone_strict(phone)
    cutoff = _ttl_cutoff(now)

    cached_log = _latest_cached_log(store=store, normalized_phone=normalized_phone, cutoff=cutoff)
    if cached_log is not None:
        return FraudCheckResult(
            cached=True,
            status=cached_log.status,
            response_json=cached_log.response_json or {},
            log_id=int(cached_log.id),
        )

    counts = _counts_for_limits(store=store, now=now)
    exceeded = _check_limits(counts=counts)
    if exceeded:
        return FraudCheckResult(
            cached=False,
            status="limit_exceeded",
            response_json={
                "detail": "Fraud check limit exceeded.",
                "limit_exceeded": exceeded,
                "counts": counts,
                "limits": {
                    "store_daily": _limit_value("STORE_DAILY_LIMIT"),
                    "store_monthly": _limit_value("STORE_MONTHLY_LIMIT"),
                    "global_daily": _limit_value("GLOBAL_DAILY_LIMIT"),
                    "global_monthly": _limit_value("GLOBAL_MONTHLY_LIMIT"),
                },
            },
            limit_exceeded=exceeded,
        )

    if not _acquire_lock(store=store, normalized_phone=normalized_phone):
        cached_log = _latest_cached_log(store=store, normalized_phone=normalized_phone, cutoff=cutoff)
        if cached_log is not None:
            return FraudCheckResult(
                cached=True,
                status=cached_log.status,
                response_json=cached_log.response_json or {},
                log_id=int(cached_log.id),
            )
        return FraudCheckResult(
            cached=False,
            status="in_progress",
            response_json={"detail": "A fraud check is already in progress for this phone number."},
        )

    try:
        api_key = (getattr(settings, "FRAUD_API_KEY", "") or "").strip()
        if not api_key:
            result = FraudCheckResult(
                cached=False,
                status="error",
                response_json={"detail": "Fraud check is not configured (missing FRAUD_API_KEY)."},
            )
            FraudCheckLog.objects.create(
                store=store,
                phone_number=(phone or "").strip(),
                normalized_phone=normalized_phone,
                response_json=result.response_json,
                status=FraudCheckLog.Status.ERROR,
            )
            return result

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {"phone": normalized_phone}

        try:
            resp = requests.post(FRAUD_CHECK_URL, json=payload, headers=headers, timeout=15)
            resp_json: dict[str, Any]
            try:
                resp_json = resp.json() if resp.content else {}
            except ValueError:
                resp_json = {"detail": "Non-JSON response from fraud API.", "text": (resp.text or "")[:5000]}

            if 200 <= resp.status_code < 300:
                status_value = FraudCheckLog.Status.SUCCESS
                stored = resp_json
            else:
                status_value = FraudCheckLog.Status.ERROR
                stored = {
                    "detail": "Fraud API returned an error.",
                    "status_code": resp.status_code,
                    "response": resp_json,
                }
        except requests.RequestException as exc:
            status_value = FraudCheckLog.Status.ERROR
            stored = {"detail": "Fraud API request failed.", "error": str(exc)}

        log = FraudCheckLog.objects.create(
            store=store,
            phone_number=(phone or "").strip(),
            normalized_phone=normalized_phone,
            response_json=stored,
            status=status_value,
        )
        return FraudCheckResult(
            cached=False,
            status=status_value,
            response_json=stored,
            log_id=int(log.id),
        )
    finally:
        _release_lock(store=store, normalized_phone=normalized_phone)

