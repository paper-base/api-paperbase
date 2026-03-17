from rest_framework.permissions import BasePermission

from engine.core.tenancy import get_active_store


class IsPlatformRequest(BasePermission):
    """Allow only platform-host requests (no tenant store derived from host)."""

    def has_permission(self, request, view):
        return bool(getattr(request, "is_platform_request", False))


class IsStaffUser(BasePermission):
    """
    Backwards-compatible permission: any authenticated Django staff.

    Kept for compatibility; prefer the store-aware classes below.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsStoreStaff(BasePermission):
    """
    Store-aware permission for dashboard endpoints.

    Requires:
    - authenticated user
    - active store resolved
    - active StoreMembership with role in {OWNER, ADMIN, STAFF}
    """

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False

        ctx = get_active_store(request)
        if not ctx.store or not ctx.membership:
            return False

        return ctx.membership.role in {
            ctx.membership.Role.OWNER,
            ctx.membership.Role.ADMIN,
            ctx.membership.Role.STAFF,
        }


class IsStoreAdmin(BasePermission):
    """
    Stricter permission for store administration operations.

    Requires role in {OWNER, ADMIN}.
    """

    def has_permission(self, request, view):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False

        ctx = get_active_store(request)
        if not ctx.store or not ctx.membership:
            return False

        return ctx.membership.role in {
            ctx.membership.Role.OWNER,
            ctx.membership.Role.ADMIN,
        }

