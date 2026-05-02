"""
Theme ownership: querysets are scoped so wrong-tenant access yields 404, not 403.
"""

from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

from config.permissions import IsAdminUser, IsStorefrontAPIKey


class ThemeGetPermission(BasePermission):
    """
    GET: valid storefront API key OR dashboard user (verified, subscribed, membership).
    Anonymous with neither → NotAuthenticated (401).
    """

    def has_permission(self, request, view):
        if getattr(request, "api_key", None) and getattr(request, "store", None):
            return IsStorefrontAPIKey().has_permission(request, view)
        if not request.user or not getattr(request.user, "is_authenticated", False):
            raise NotAuthenticated()
        return IsAdminUser().has_permission(request, view)


class PresetsViewPermission(BasePermission):
    """Authenticated users only (dashboard JWT or session)."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False))


class IsThemeOwner(BasePermission):
    """
    Object-level: theme.store must match the active store for this request.
    Used as defense-in-depth with scoped get_object (wrong tenant → 404).
    """

    def has_object_permission(self, request, view, obj):
        from engine.core.tenancy import get_active_store

        ctx = get_active_store(request)
        store = ctx.store
        if store is None:
            return False
        return int(getattr(obj, "store_id", 0) or 0) == int(store.pk)
