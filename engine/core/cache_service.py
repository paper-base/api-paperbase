"""
Tenant-scoped cache-aside service for frequently accessed store data.

All cache keys include store context to guarantee tenant isolation.
Internal database IDs are never used in keys — only public_ids.

Uses the Django ``default`` cache backend (Redis in production, LocMem in
development) so no extra dependencies are required.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)


def build_key(store_public_id: str, resource: str, identifier: str = "") -> str:
    """
    Build a tenant-scoped cache key.

    Format: ``cache:{store_public_id}:{resource}:{identifier}``
    """
    if identifier:
        return f"cache:{store_public_id}:{resource}:{identifier}"
    return f"cache:{store_public_id}:{resource}"


def build_user_key(user_public_id: str, resource: str) -> str:
    """Build a user-scoped cache key (for non-store data like feature config)."""
    return f"cache:user:{user_public_id}:{resource}"


def hash_params(params: dict[str, Any]) -> str:
    """Deterministic short hash of query parameters for use in cache keys."""
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def get(key: str) -> Any:
    """Retrieve a value from cache, returning ``None`` on miss."""
    try:
        raw = cache.get(key)
    except Exception:
        logger.warning("cache get failed for %s", key, exc_info=True)
        return None
    if raw is None:
        return None
    return _deserialize(raw)


def set(key: str, value: Any, ttl: int) -> None:  # noqa: A001
    """Store a JSON-serializable value with the given TTL (seconds)."""
    try:
        cache.set(key, json.dumps(value, default=str), ttl)
    except Exception:
        logger.warning("cache set failed for %s", key, exc_info=True)


def delete(key: str) -> None:
    """Remove a single cache key."""
    try:
        cache.delete(key)
    except Exception:
        logger.warning("cache delete failed for %s", key, exc_info=True)


def delete_many(keys: list[str]) -> None:
    """Remove multiple cache keys."""
    if not keys:
        return
    try:
        cache.delete_many(keys)
    except Exception:
        logger.warning("cache delete_many failed", exc_info=True)


def get_or_set(key: str, fetch_fn: Callable[[], Any], ttl: int) -> Any:
    """
    Cache-aside: return cached value if present, otherwise call *fetch_fn*,
    store the result, and return it.

    Cache errors are non-fatal — on failure the fetcher is always called.
    """
    cached = get(key)
    if cached is not None:
        return cached
    value = fetch_fn()
    if value is not None:
        set(key, value, ttl)
    return value


def invalidate_store_resource(store_public_id: str, resource: str) -> None:
    """
    Delete all cache entries for a given store + resource prefix.

    Uses Redis ``SCAN`` when available (production) and falls back to a
    single-prefix delete for LocMem (development).
    """
    pattern = f"cache:{store_public_id}:{resource}:*"
    fallback_key = build_key(store_public_id, resource)

    try:
        backend = cache
        # Django 5's RedisCache exposes _cache (RedisCacheClient) which holds
        # the connection pool.  We reach through to run SCAN safely.
        redis_cache_client = getattr(backend, "_cache", None)
        if redis_cache_client is not None and hasattr(redis_cache_client, "get_client"):
            _redis_scan_delete(redis_cache_client, pattern)
            return
    except Exception:
        logger.warning("Redis SCAN invalidation failed for %s", pattern, exc_info=True)

    # LocMem / fallback: delete the exact key (pattern matching unsupported).
    delete(fallback_key)


def invalidate_user_resource(user_public_id: str, resource: str) -> None:
    """Delete a user-scoped cache key."""
    delete(build_user_key(user_public_id, resource))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deserialize(raw: Any) -> Any:
    """Normalise a cached value back to a Python object."""
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    if isinstance(raw, memoryview):
        raw = raw.tobytes().decode()
    if isinstance(raw, bytes):
        raw = raw.decode()
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


def _redis_scan_delete(redis_cache_client: Any, pattern: str) -> None:
    """Use Redis SCAN to find and delete keys matching *pattern*."""
    client = redis_cache_client.get_client()

    # Django's RedisCache may apply a key prefix/version; we need the raw
    # Redis key with the prefix included.
    key_prefix = getattr(redis_cache_client, "key_func", None)
    if key_prefix is None:
        key_prefix = getattr(redis_cache_client, "_key_func", None)

    # Build the Redis-level pattern.  Django 5's default key function is
    # ``make_key`` which prepends ``:{version}:{key}`` — but the backend
    # also exposes ``make_key`` directly.
    make_key = getattr(redis_cache_client, "make_key", None)
    if make_key is not None:
        # Replace the trailing wildcard temporarily so make_key can process it
        # then re-append.
        redis_pattern = make_key(pattern.rstrip("*")) + "*"
    else:
        redis_pattern = pattern

    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match=redis_pattern, count=100)
        if keys:
            client.delete(*keys)
        if cursor == 0:
            break
