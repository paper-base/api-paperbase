"""
Rate limits for tenant domain resolution (HTTP + WebSocket).

Uses Django cache with keys rate:ip:{ip} and rate:domain:{host} so tests work with LocMem.
"""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin


def _tenant_resolution_cache():
    alias = getattr(settings, "TENANT_RESOLUTION_CACHE_ALIAS", "tenant_resolution")
    return caches[alias]


def _normalize_host(host: str) -> str:
    if not host:
        return ""
    return host.split(":", 1)[0].lower()


def _client_ip(request: HttpRequest) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _rate_window_seconds() -> int:
    return 60


def _incr_under_limit(cache_key: str, limit: int) -> bool:
    """
    Increment a fixed-window counter. Returns True if under or at limit, False if exceeded.
    """
    if limit <= 0:
        return True
    window = _rate_window_seconds()
    c = _tenant_resolution_cache()
    try:
        n = c.incr(cache_key)
    except ValueError:
        c.set(cache_key, 1, window)
        n = 1
    return n <= limit


def tenant_resolution_rate_check(ip: str, normalized_host: str) -> bool:
    """
    Apply IP + domain buckets. Returns True if request is allowed, False if rate limited.
    """
    ip_limit = int(getattr(settings, "TENANT_RESOLUTION_RATE_LIMIT_IP", 120))
    dom_limit = int(getattr(settings, "TENANT_RESOLUTION_RATE_LIMIT_DOMAIN", 60))
    if not _incr_under_limit(f"rate:ip:{ip}", ip_limit):
        return False
    if normalized_host and not _incr_under_limit(f"rate:domain:{normalized_host}", dom_limit):
        return False
    return True


class TenantResolutionRateLimitMiddleware(MiddlewareMixin):
    """
    On non-platform hosts, rate-limit by client IP and Host before tenant resolution.
    """

    def process_request(self, request: HttpRequest):
        host = _normalize_host(request.get_host())
        platform_hosts = {h.lower() for h in getattr(settings, "PLATFORM_HOSTS", [])}
        if host in platform_hosts:
            return None
        path = request.path
        exempt = getattr(settings, "TENANT_RATE_LIMIT_EXEMPT_PATH_PREFIXES", ())
        if any(path.startswith(p) for p in exempt):
            return None
        ip = _client_ip(request)
        if not tenant_resolution_rate_check(ip, host):
            return JsonResponse({"detail": "Too many requests."}, status=429)
        return None


class WebSocketResolutionRateLimitMiddleware:
    """ASGI: same limits as HTTP tenant resolution for WebSocket handshakes."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await self.inner(scope, receive, send)
        headers = dict(scope.get("headers", []))
        raw = headers.get(b"host", b"").decode("latin1")
        host = _normalize_host(raw)
        platform_hosts = {h.lower() for h in getattr(settings, "PLATFORM_HOSTS", [])}
        if host in platform_hosts:
            return await self.inner(scope, receive, send)
        client = scope.get("client")
        ip = client[0] if client else "unknown"
        allowed = await sync_to_async(tenant_resolution_rate_check)(ip, host)
        if not allowed:
            await send({"type": "websocket.close", "code": 1008})
            return
        return await self.inner(scope, receive, send)
