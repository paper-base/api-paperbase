from __future__ import annotations

from dataclasses import dataclass

from django.utils.deprecation import MiddlewareMixin

from engine.core.authz import can_enable_internal_override


def _client_ip(request) -> str:
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


@dataclass(frozen=True)
class AuthContext:
    internal_override_enabled: bool
    client_ip: str


class InternalOverrideMiddleware(MiddlewareMixin):
    """
    Build trusted override context from authenticated identity + allowlisted IP.
    """

    def process_request(self, request):
        user = getattr(request, "user", None)
        client_ip = _client_ip(request)
        enabled = can_enable_internal_override(user=user, client_ip=client_ip)
        request.auth_context = AuthContext(
            internal_override_enabled=enabled,
            client_ip=client_ip,
        )
        return None
