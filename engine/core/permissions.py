"""Shared permission classes for e-commerce engine apps."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsModuleEnabled(BasePermission):
    """
    Gate a view behind a boolean flag in ``StoreSettings.modules_enabled``.

    Subclasses (or views) set ``module_key`` to the flag name (e.g. ``"blog"``).
    Returns 403 when the active store exists but the flag is falsy, or when no
    store context is resolved. Intended to be combined with the usual tenant
    / auth permission classes — it only checks the module flag.
    """

    module_key: str = ""
    message = "This module is disabled for the current store."

    def has_permission(self, request, view):
        from engine.core.tenancy import get_active_store

        key = getattr(view, "module_key", None) or self.module_key
        if not key:
            return True
        ctx = get_active_store(request)
        store = ctx.store
        if store is None:
            return False
        settings_row = getattr(store, "settings", None)
        raw = getattr(settings_row, "modules_enabled", {}) if settings_row else {}
        modules = raw if isinstance(raw, dict) else {}
        return bool(modules.get(key, False))


class IsOwnerOrReadOnly(BasePermission):
    """Allow read to anyone; write only to the resource owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, 'user', None) or getattr(obj, 'customer', None)
        if owner is None:
            # Deny write when no owner field is present — fail closed.
            return False
        user = request.user
        if not user.is_authenticated:
            return False
        if hasattr(owner, 'user_id'):
            return owner.user_id == user.pk
        return owner.pk == user.pk
