"""Store-scoped helpers used by billing, emails, and serializers."""

from django.contrib.auth import get_user_model

from engine.apps.billing.feature_gate import has_feature

from .models import Store, StoreMembership, StoreSettings

User = get_user_model()

ORDER_EMAIL_NOTIFICATIONS_FEATURE = "order_email_notifications"


def get_store_owner_user(store: Store) -> User | None:
    """Active OWNER membership user for the store, or None."""
    m = (
        StoreMembership.objects.filter(
            store=store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )
        .select_related("user")
        .first()
    )
    return m.user if m else None


def sync_store_owner_to_user(store: Store) -> None:
    """When Store.owner_name changes, mirror it onto the owner User first/last name."""
    owner = get_store_owner_user(store)
    if not owner:
        return
    raw = (store.owner_name or "").strip()
    if not raw:
        return
    parts = raw.split(None, 1)
    first = (parts[0] or "")[:150]
    last = (parts[1] if len(parts) > 1 else "")[:150]
    if owner.first_name == first and owner.last_name == last:
        return
    owner.first_name = first
    owner.last_name = last
    owner.save(update_fields=["first_name", "last_name"])


def sync_order_email_notification_settings_for_user(user) -> None:
    """
    When the user loses premium order-email entitlement, disable both flags
    on every store they own.
    """
    if has_feature(user, ORDER_EMAIL_NOTIFICATIONS_FEATURE):
        return
    store_ids = StoreMembership.objects.filter(
        user=user,
        role=StoreMembership.Role.OWNER,
        is_active=True,
    ).values_list("store_id", flat=True)
    for store_id in store_ids:
        StoreSettings.objects.update_or_create(
            store_id=store_id,
            defaults={
                "email_notify_owner_on_order_received": False,
                "email_customer_on_order_confirmed": False,
            },
        )
