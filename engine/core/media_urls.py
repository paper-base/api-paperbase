"""Absolute URLs for FileField/ImageField in API responses."""

from __future__ import annotations

from typing import Any


def absolute_media_url(file_field: Any, request) -> str | None:
    """Return an absolute URL for a Django FileField/ImageField, or None if empty."""
    if not file_field or not getattr(file_field, "name", None):
        return None
    url = file_field.url
    if request:
        return request.build_absolute_uri(url)
    return url
