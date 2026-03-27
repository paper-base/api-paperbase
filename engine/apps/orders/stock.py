from __future__ import annotations

from django.core.exceptions import ValidationError

from engine.apps.inventory.models import StockMovement
from engine.apps.inventory.services import adjust_inventory_stock


def adjust_stock(*, store_id: int, product_id, variant_id: int | None = None, delta_qty: int) -> None:
    """
    Adjust inventory for an order item.

    - delta_qty > 0: reduce stock (reserve/consume)
    - delta_qty < 0: restore stock (e.g. item removed or quantity lowered)
    """
    if store_id is None:
        raise ValidationError({"store": "store_id is required."})
    try:
        adjust_inventory_stock(
            store_id=store_id,
            product_id=product_id,
            variant_id=variant_id,
            delta_qty=int(delta_qty),
            reason=StockMovement.Reason.SALE if int(delta_qty) > 0 else StockMovement.Reason.RETURN,
            source=StockMovement.Source.ORDER,
            reference_id="",
            reference="order-item-adjustment",
            actor=None,
        )
    except ValidationError:
        raise

