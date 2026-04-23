"""Throttle classes for tracking ingest endpoints."""
from rest_framework.throttling import AnonRateThrottle


class TrackingIngestThrottle(AnonRateThrottle):
    """
    IP-based rate limit for the tracking event ingest endpoint.

    Uses client IP (respecting NUM_PROXIES) as the cache key so this fires
    before any API key lookup hits the database, protecting against bot floods
    and invalid-key probing at the network edge.
    """

    scope = "tracking_ingest"
