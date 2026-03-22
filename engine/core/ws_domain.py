"""Resolve tenant store public_id from WebSocket Host header."""

from __future__ import annotations

from asgiref.sync import sync_to_async

from engine.core.tenancy import resolve_store_public_id_from_host_header


class DomainWebSocketMiddleware:
    """Attach scope[\"store_public_id\"] from verified Domain + active store."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await self.inner(scope, receive, send)
        headers = dict(scope.get("headers", []))
        raw = headers.get(b"host", b"").decode("latin1")
        host = raw.split(":", 1)[0].lower()
        store_public_id = await sync_to_async(resolve_store_public_id_from_host_header)(host)
        scope["store_public_id"] = store_public_id
        return await self.inner(scope, receive, send)
