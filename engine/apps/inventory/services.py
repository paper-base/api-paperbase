"""Inventory services: tenant-safe stock adjustment and audit logging."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from engine.core.tenant_context import require_store_context
from .cache_sync import refresh_product_stock_cache
from .utils import clamp_stock


def _lock_inventory(*, store_id: int, product_id, variant_id: int | None):
    from .models import Inventory
    from engine.apps.products.models import ProductVariant

    # Avoid JOINs in SELECT ... FOR UPDATE on nullable relations (Postgres disallows
    # locking the nullable side of an outer join).
    qs = Inventory.objects.select_for_update()
    if variant_id is None:
        return qs.get(
            product_id=product_id,
            variant__isnull=True,
        )
    inventory = qs.get(
        product_id=product_id,
        variant_id=variant_id,
    )
    if not ProductVariant.objects.filter(id=variant_id, product_id=product_id).exists():
        raise Inventory.DoesNotExist
    return inventory


def adjust_inventory_stock(
    *,
    store_id: int,
    product_id,
    variant_id: int | None,
    delta_qty: int,
    reason: str,
    source: str,
    reference_id: str = "",
    reference: str = "",
    actor=None,
    allow_negative: bool = False,
):
    """
    Tenant-scoped stock mutation entrypoint.
    Positive delta reduces available inventory, negative delta restores it.
    """
    from engine.apps.products.models import Product
    from .models import Inventory, StockMovement

    if delta_qty is None:
        raise ValidationError("delta_qty is required.")
    delta_qty = int(delta_qty)
    if delta_qty == 0:
        raise ValidationError("delta_qty must be non-zero.")

    with transaction.atomic():
        try:
            Product.objects.select_for_update().get(id=product_id, store_id=store_id)
        except Product.DoesNotExist as exc:
            raise ValidationError("Invalid product for this store.") from exc

        try:
            inventory = _lock_inventory(store_id=store_id, product_id=product_id, variant_id=variant_id)
        except Inventory.DoesNotExist as exc:
            raise ValidationError("Invalid product for this store.") from exc

        current_quantity = int(inventory.quantity)
        next_quantity = current_quantity - delta_qty
        clamped_next_quantity = clamp_stock(next_quantity)
        applied_change = clamped_next_quantity - current_quantity

        Inventory.objects.filter(pk=inventory.pk).update(quantity=clamped_next_quantity)
        inventory.refresh_from_db(fields=["quantity", "updated_at"])

        StockMovement.objects.create(
            inventory=inventory,
            change=applied_change,
            reason=reason,
            source=source,
            reference_id=(reference_id or "")[:100],
            reference=(reference or "")[:255],
            actor=actor,
        )
        if inventory.is_low_stock() and inventory.quantity <= inventory.low_stock_threshold:
            _create_low_stock_notification(inventory)

        refresh_product_stock_cache(store_id=int(store_id), product_id=product_id)
        return inventory


def adjust_stock(
    inventory,
    change,
    reason="adjustment",
    source="admin",
    reference_id="",
    reference="",
    actor=None,
):
    """
    Backward-compatible inventory-row adjust wrapper for admin adjust endpoint.
    """
    return adjust_inventory_stock(
        store_id=inventory.product.store_id,
        product_id=inventory.product_id,
        variant_id=inventory.variant_id,
        delta_qty=-int(change),
        reason=reason,
        source=source,
        reference_id=reference_id,
        reference=reference,
        actor=actor,
    )


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
