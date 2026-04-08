"""
DRF integration: bind tenant ContextVar after authentication (JWT/session).
"""

from __future__ import annotations

from rest_framework.request import Request

from engine.core.tenancy import bind_validated_tenant_context


class ProvenTenantContextMixin:
    """
    After DRF authenticates the request, mirror proven tenant resolution to ContextVar.

    Dashboard views that rely on TenantAwareManager or tenant guards should inherit this mixin.
    """

    def initial(self, request: Request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        bind_validated_tenant_context(request._request)
