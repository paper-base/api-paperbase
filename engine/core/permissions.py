"""Shared permission classes for e-commerce engine apps."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnly(BasePermission):
    """Allow read to anyone; write only to the resource owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, 'user', None) or getattr(obj, 'customer', None)
        if owner is None:
            return True
        user = request.user
        if not user.is_authenticated:
            return False
        if hasattr(owner, 'user_id'):
            return owner.user_id == user.pk
        return owner.pk == user.pk
