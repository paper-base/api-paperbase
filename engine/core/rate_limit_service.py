"""
Centralized cooldown-based rate limiting for sensitive actions.

Uses Django's default cache (Redis in production, LocMem in development).
Complements DRF throttles which handle request-count limiting.

Key format: rate:{scope}:{action}:{identifier}
  - scope = store public_id for tenant-scoped actions, "platform" for auth actions
  - action = registry key (e.g. "password_reset")
  - identifier = email, IP, or other per-action identifier
"""

from __future__ import annotations

import time

from django.core.cache import cache


RATE_LIMITS: dict[str, dict] = {
    "password_reset": {"cooldown": 120},
    "email_verification_resend": {"cooldown": 120},
    "2fa_recovery_request": {"cooldown": 120},
}


class RateLimitExceeded(Exception):
    """Raised when a cooldown-based rate limit is active for the requested action."""

    def __init__(self, action: str, retry_after: int):
        self.action = action
        self.retry_after = retry_after
        super().__init__(f"Rate limited: {action}")

    def as_response_data(self) -> dict:
        return {
            "error": "rate_limited",
            "action": self.action,
            "retry_after": self.retry_after,
        }


def _build_key(store_id: str | None, action: str, identifier: str) -> str:
    scope = store_id or "platform"
    safe_identifier = (identifier or "").strip().lower()
    return f"rate:{scope}:{action}:{safe_identifier}"


def check_rate_limit(
    store_id: str | None, action: str, identifier: str
) -> tuple[bool, int]:
    """
    Check whether a cooldown is active.

    Returns (is_allowed, retry_after_seconds).
    """
    config = RATE_LIMITS.get(action)
    if not config:
        return True, 0

    key = _build_key(store_id, action, identifier)
    expires_at = cache.get(key)
    if expires_at is not None:
        remaining = max(0, int(expires_at - time.time()))
        if remaining > 0:
            return False, remaining

    return True, 0


def enforce_rate_limit(
    store_id: str | None, action: str, identifier: str
) -> None:
    """Raise ``RateLimitExceeded`` if a cooldown is still active."""
    allowed, retry_after = check_rate_limit(store_id, action, identifier)
    if not allowed:
        raise RateLimitExceeded(action, retry_after)


def record_action(
    store_id: str | None, action: str, identifier: str
) -> None:
    """Start the cooldown timer after a successful action."""
    config = RATE_LIMITS.get(action)
    if not config:
        return
    cooldown = config["cooldown"]
    key = _build_key(store_id, action, identifier)
    cache.set(key, time.time() + cooldown, cooldown)


def get_retry_after(
    store_id: str | None, action: str, identifier: str
) -> int:
    """Return remaining cooldown seconds (0 if not rate-limited)."""
    _, retry_after = check_rate_limit(store_id, action, identifier)
    return retry_after
