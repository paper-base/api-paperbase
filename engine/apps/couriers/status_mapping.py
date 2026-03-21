"""
Map courier API status strings to platform order lifecycle.

Pathao/Steadfast return provider-specific labels; tune these sets against real API responses.
Normalized comparison: lowercase, stripped, spaces → underscores.
"""

from __future__ import annotations

from engine.apps.couriers.models import Courier


def _normalize(raw: str) -> str:
    return (raw or "").strip().lower().replace(" ", "_").replace("-", "_")


# Statuses meaning the parcel has been handed off to the courier network (merchant → courier).
# Tune against real Pathao/Steadfast API values in production.
_PATHAO_HANDOFF = frozenset(
    {
        "picked_up",
        "pickup",
        "at_pickup",
        "at_hub",
        "at_hub_processing",
        "in_transit",
        "on_way",
        "on_the_way",
        "delivered_to_hub",
    }
)

_STEADFAST_HANDOFF = frozenset(
    {
        "picked_up",
        "pickup",
        "at_hub",
        "in_transit",
        "on_way",
        "delivered_to_hub",
    }
)


def courier_status_implies_order_confirmed(provider: str, raw_status: str) -> bool:
    """Return True if courier reports handoff so the store order should become `confirmed`."""
    key = _normalize(raw_status)
    if not key:
        return False
    if provider == Courier.Provider.PATHAO:
        return key in _PATHAO_HANDOFF
    if provider == Courier.Provider.STEADFAST:
        return key in _STEADFAST_HANDOFF
    return False
