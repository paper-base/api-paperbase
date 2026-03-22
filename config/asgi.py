"""
ASGI config: HTTP (Django) + WebSocket (Channels) with tenant domain + JWT middleware.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

from engine.core.rate_limit import WebSocketResolutionRateLimitMiddleware
from engine.core.routing import websocket_urlpatterns
from engine.core.ws_auth import JWTStoreWebSocketMiddleware
from engine.core.ws_domain import DomainWebSocketMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            WebSocketResolutionRateLimitMiddleware(
                DomainWebSocketMiddleware(
                    JWTStoreWebSocketMiddleware(
                        URLRouter(websocket_urlpatterns),
                    )
                )
            )
        ),
    }
)
