from django.urls import path

from engine.core.consumers import StoreEventsConsumer

websocket_urlpatterns = [
    path("ws/v1/store/events/", StoreEventsConsumer.as_asgi()),
]
