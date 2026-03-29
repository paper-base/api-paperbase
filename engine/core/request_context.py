from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.apps.stores.models import Store


@dataclass(frozen=True)
class RequestContext:
    """HTTP request execution context: tenant isolation vs platform-wide access."""

    tenant: Store | None = None
    is_platform_admin: bool = False


def user_enters_platform_scope(user) -> bool:
    """
    Whether the authenticated user operates in platform (global) scope.

    Extend here for support/analytics roles without scattering checks.
    """
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_superuser", False)
    )
