"""Throttle classes for order endpoints."""
from rest_framework.throttling import AnonRateThrottle


class DirectOrderRateThrottle(AnonRateThrottle):
    scope = "direct_order"
