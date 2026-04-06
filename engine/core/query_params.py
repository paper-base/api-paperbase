"""Shared query parameter parsing for admin APIs."""


def include_inactive_truthy(request) -> bool:
    """True when ?include_inactive=1|true|yes (case-insensitive)."""
    v = (request.query_params.get("include_inactive") or "").strip().lower()
    return v in ("1", "true", "yes")
