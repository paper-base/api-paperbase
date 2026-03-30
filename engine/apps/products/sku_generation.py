"""Central variant SKU generation: SKU-{tenant}-{unix_ts}-{random} per store."""

from __future__ import annotations

import logging
import re
import secrets
import time

from engine.apps.stores.models import Store

logger = logging.getLogger(__name__)

_RANDOM_MIN = 1_000
_RANDOM_MAX = 999_999


class SkuGenerationError(Exception):
    """Raised when a unique SKU cannot be allocated after retries."""


def tenant_segment_from_store(store: Store) -> str:
    """Stable tenant segment from Store.code only (slug must not affect SKUs)."""
    raw = (getattr(store, "code", None) or "").strip().upper()
    seg = re.sub(r"[^A-Z0-9]", "", raw)[:10]
    if not seg:
        raise ValueError("Store.code is required for SKU generation. Missing tenant code.")
    return seg


def build_sku_candidate(store: Store) -> str:
    """Single candidate string; uniqueness is enforced only by the database."""
    tenant = tenant_segment_from_store(store)
    ts = int(time.time())
    rnd = secrets.randbelow(_RANDOM_MAX - _RANDOM_MIN + 1) + _RANDOM_MIN
    return f"SKU-{tenant}-{ts}-{rnd}"


def log_variant_sku_generation(
    *,
    store_id: int,
    store_code: str,
    generated_sku: str,
    attempt_number: int,
    outcome: str,
    exception: str | None = None,
    level: str,
    exc_info: BaseException | None = None,
) -> None:
    extra = {
        "event": "variant_sku_generation",
        "store_id": store_id,
        "store_code": store_code,
        "generated_sku": generated_sku,
        "attempt_number": attempt_number,
        "outcome": outcome,
        "exception": exception or "",
    }
    msg = "variant_sku_generation"
    if level == "debug":
        logger.debug(msg, extra=extra)
    elif level == "error":
        log_kwargs: dict = {"extra": extra}
        if exc_info is not None:
            log_kwargs["exc_info"] = exc_info
        logger.error(msg, **log_kwargs)
    else:
        logger.info(msg, extra=extra)


# Backwards compatibility for any external imports
def tenant_short_from_store(store: Store) -> str:
    return tenant_segment_from_store(store)


def generate_sku(store: Store) -> str:
    """Build one candidate (no DB pre-check); callers should rely on constraint + retry."""
    return build_sku_candidate(store)
