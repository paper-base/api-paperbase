"""
Inventory services: stock adjustments and low-stock notifications.
"""
from django.db import transaction
from django.core.exceptions import ValidationError

from engine.core.tenant_context import require_store_context

def adjust_stock(inventory, change, reason='adjustment', reference='', actor=None):
    """
    Adjust inventory quantity and record a StockMovement.
    Optionally create a StaffInboxNotification when stock falls at or below low_stock_threshold.
    """
    from .models import Inventory, StockMovement

    with transaction.atomic():
        inventory.quantity = max(0, inventory.quantity + change)
        inventory.save(update_fields=['quantity', 'updated_at'])
        StockMovement.objects.create(
            inventory=inventory,
            change=change,
            reason=reason,
            reference=reference,
            actor=actor,
        )
        if inventory.is_low_stock() and inventory.quantity <= inventory.low_stock_threshold:
            _create_low_stock_notification(inventory)


def _create_low_stock_notification(inventory):
    """Create a tenant-scoped low-stock notification for a concrete recipient."""
    try:
        from engine.apps.accounts.models import User
        from engine.apps.notifications.models import StaffNotification
        from engine.apps.stores.models import StoreMembership

        store = require_store_context()
        if inventory.product.store_id != store.id:
            raise ValidationError("Inventory store does not match current tenant context.")

        recipient = (
            User.objects.filter(
                store_memberships__store=store,
                store_memberships__is_active=True,
                store_memberships__role__in=[
                    StoreMembership.Role.OWNER,
                    StoreMembership.Role.ADMIN,
                    StoreMembership.Role.STAFF,
                ],
            )
            .order_by("id")
            .first()
        )
        if recipient is None:
            return

        title = f"Low stock: {inventory.product.name}"
        if inventory.variant_id:
            title += f" ({inventory.variant.sku or f'Variant {inventory.variant_id}'})"
        StaffNotification.objects.create(
            store=store,
            user=recipient,
            message_type=StaffNotification.MessageType.LOW_STOCK,
            title=title,
            payload={
                'product_id': str(inventory.product_id),
                'variant_id': inventory.variant_id,
                'quantity': inventory.quantity,
                'threshold': inventory.low_stock_threshold,
            },
        )
    except Exception:
        pass  # Do not fail stock update if notification fails
