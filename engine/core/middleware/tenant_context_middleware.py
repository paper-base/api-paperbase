from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from engine.core.store_session import resolve_store_session
from engine.core.tenancy import get_active_store
from engine.core.tenant_context import _clear_tenant_context, _set_tenant_context


class TenantContextMiddleware(MiddlewareMixin):
    """
    Persist request-scoped tenant context as the single source of truth.
    """

    def process_request(self, request):
        ctx = get_active_store(request)
        session_id = None
        if ctx.store is not None and getattr(request, "api_key", None):
            session_ctx = resolve_store_session(request)
            session_id = session_ctx.store_session_id
        token = _set_tenant_context(store=ctx.store, session_id=session_id)
        request._tenant_context_token = token
        return None

    def process_response(self, request, response):
        _clear_tenant_context()
        return response

    def process_exception(self, request, exception):
        _clear_tenant_context()
        return None
