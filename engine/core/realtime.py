"""
Push store-scoped events to WebSocket groups (Channels).

Group name: store_{store_public_id}. Never derive group from untrusted client input.
"""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def emit_store_event(store_public_id: str, event_type: str, payload: dict) -> None:
    """Fan-out to all connections in the store channel group."""
    if not store_public_id or not event_type:
        return
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"store_{store_public_id}",
        {
            "type": "store.event",
            "event": event_type,
            "payload": payload or {},
        },
    )
