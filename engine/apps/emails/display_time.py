"""Display formatting for transactional email copy (GMT+6, no DST)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from django.utils import timezone as dj_tz

# Standard display zone for all customer-facing email timestamps (GMT+6, no DST).
EMAIL_DISPLAY_TZ = timezone(timedelta(hours=6))


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dj_tz.is_naive(dt):
        return dj_tz.make_aware(dt, dj_tz.utc)
    return dt


def format_email_datetime(dt: datetime | None = None) -> str:
    """
    Format an instant as DD-MM-YYYY HH:MM (24h) in GMT+6.
    Used for event times, expiries, and timestamps in email bodies.
    """
    if dt is None:
        dt = dj_tz.now()
    return _ensure_aware_utc(dt).astimezone(EMAIL_DISPLAY_TZ).strftime("%d-%m-%Y %H:%M")


def format_email_date_in_display_tz(dt: datetime | date | None = None) -> str:
    """
    Calendar date as DD-MM-YYYY.
    For datetime values, uses the calendar date in GMT+6; for date values, formats as-is.
    """
    if dt is None:
        d = dj_tz.now().astimezone(EMAIL_DISPLAY_TZ).date()
    elif isinstance(dt, datetime):
        d = _ensure_aware_utc(dt).astimezone(EMAIL_DISPLAY_TZ).date()
    elif isinstance(dt, date):
        d = dt
    else:
        d = dj_tz.now().astimezone(EMAIL_DISPLAY_TZ).date()
    return d.strftime("%d-%m-%Y")
