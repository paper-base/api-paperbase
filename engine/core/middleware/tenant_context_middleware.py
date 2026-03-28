from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from engine.core.tenancy import get_active_store
from engine.core.tenant_context import _clear_tenant_context, _set_tenant_context


class TenantContextMiddleware(MiddlewareMixin):
    """
    Persist request-scoped tenant context as the single source of truth.
    """

    def process_request(self, request):
        ctx = get_active_store(request)
        token = _set_tenant_context(store=ctx.store)
        request._tenant_context_token = token
        return None

    def process_response(self, request, response):
        _clear_tenant_context()
        return response

    def process_exception(self, request, exception):
        _clear_tenant_context()
        return None
