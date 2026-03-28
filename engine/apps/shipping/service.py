from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError

from engine.apps.stores.models import Store
from engine.core import cache_service

from .models import ShippingMethod, ShippingRate, ShippingZone

@dataclass(frozen=True)
class ShippingQuote:
    shipping_cost: Decimal
    method: ShippingMethod | None = None
    rate: ShippingRate | None = None
    zone: ShippingZone | None = None


def quote_shipping(
    *,
    store: Store,
    order_subtotal: Decimal,
    shipping_zone_id: int | None,
    shipping_method_id: int | None = None,
) -> ShippingQuote:
    """
    Return the best matching shipping quote for a zone-selected order.
    """
    if shipping_zone_id is None:
        raise ValidationError("Shipping zone is required.")

    zone = ShippingZone.objects.filter(
        store=store,
        is_active=True,
        id=shipping_zone_id,
    ).first()
    if zone is None:
        raise ValidationError("Invalid shipping zone for this store.")

    methods = (
        ShippingMethod.objects.filter(store=store, is_active=True)
        .prefetch_related("zones")
        .order_by("order", "id")
    )
    if shipping_method_id is not None:
        methods = methods.filter(id=shipping_method_id)

    best: ShippingQuote | None = None

    for method in methods:
        method_zone_ids = set(method.zones.values_list("id", flat=True))
        if method_zone_ids and zone.id not in method_zone_ids:
            continue

        rates = (
            ShippingRate.objects.filter(
                store=store,
                is_active=True,
                shipping_method=method,
                shipping_zone=zone,
            )
            .select_related("shipping_zone", "shipping_method")
            .order_by("price", "id")
        )
        for rate in rates:
            if rate.min_order_total is not None and order_subtotal < rate.min_order_total:
                continue
            if rate.max_order_total is not None and order_subtotal > rate.max_order_total:
                continue
            quote = ShippingQuote(
                shipping_cost=rate.price,
                method=method,
                rate=rate,
                zone=rate.shipping_zone,
            )
            if best is None:
                best = quote
            else:
                if quote.shipping_cost < best.shipping_cost:
                    best = quote
                elif quote.shipping_cost == best.shipping_cost:
                    if (quote.method.order, quote.method.id) < (best.method.order, best.method.id):  # type: ignore[union-attr]
                        best = quote
            break

    return best or ShippingQuote(shipping_cost=Decimal("0.00"), zone=zone)


# ---------------------------------------------------------------------------
# Storefront shipping options (cached)
# ---------------------------------------------------------------------------

def get_shipping_options(store, zone_public_id: str, order_total_str: str | None):
    """
    Return cached shipping options for a zone, falling back to DB.
    Returns a list of option dicts ready for serialization.
    """
    from .serializers import ShippingOptionSerializer

    params = {"zone": zone_public_id, "order_total": order_total_str or ""}
    key = cache_service.build_key(
        store.public_id,
        "shipping_options",
        cache_service.hash_params(params),
    )

    def fetcher():
        try:
            order_total = Decimal(order_total_str) if order_total_str else None
        except Exception:
            order_total = None

        zone = ShippingZone.objects.filter(
            store=store, is_active=True, public_id=zone_public_id
        ).first()
        if zone is None:
            return []

        methods = ShippingMethod.objects.filter(
            store=store, is_active=True
        ).prefetch_related("rates__shipping_zone").distinct()

        options = []
        for method in methods:
            method_zone_ids = set(method.zones.values_list("id", flat=True))
            if method_zone_ids and zone.id not in method_zone_ids:
                continue
            for rate in method.rates.filter(
                store=store, is_active=True
            ).select_related("shipping_zone"):
                if rate.shipping_zone_id != zone.id:
                    continue
                if order_total is not None:
                    if rate.min_order_total and order_total < rate.min_order_total:
                        continue
                    if rate.max_order_total and order_total > rate.max_order_total:
                        continue
                options.append(
                    {
                        "method_public_id": method.public_id,
                        "method_name": method.name,
                        "zone_public_id": rate.shipping_zone.public_id,
                        "zone_name": rate.shipping_zone.name,
                        "price": rate.price,
                        "rate_type": rate.rate_type,
                    }
                )
        return ShippingOptionSerializer(options, many=True).data

    return cache_service.get_or_set(key, fetcher, settings.CACHE_TTL_SHIPPING_OPTIONS)


def invalidate_shipping_cache(store_public_id: str) -> None:
    """Clear shipping option caches for a store."""
    cache_service.invalidate_store_resource(store_public_id, "shipping_options")


# ---------------------------------------------------------------------------
# Storefront: zone catalog + line-items preview
# ---------------------------------------------------------------------------


def build_shipping_zones_catalog(store: Store) -> list[dict]:
    """
    List active zones with estimated delivery text and merged cost bands.

    For each distinct (min_order_total, max_order_total) band on rates that
    apply to the zone (and method-zone eligibility), expose the lowest price.
    """
    zones = ShippingZone.objects.filter(store=store, is_active=True).order_by("name")
    out: list[dict] = []
    for zone in zones:
        out.append(
            {
                "id": zone.public_id,
                "name": zone.name,
                "estimated_days": zone.estimated_delivery_text or "",
                "cost_rules": _zone_cost_rules(store, zone),
            }
        )
    return out


def _zone_cost_rules(store: Store, zone: ShippingZone) -> list[dict]:
    best: dict[tuple[Decimal, Decimal | None], Decimal] = {}
    rates = (
        ShippingRate.objects.filter(
            store=store, is_active=True, shipping_zone=zone
        )
        .select_related("shipping_method")
        .order_by("price", "id")
    )
    for rate in rates:
        method = rate.shipping_method
        if not method.is_active:
            continue
        method_zone_ids = set(method.zones.values_list("id", flat=True))
        if method_zone_ids and zone.id not in method_zone_ids:
            continue
        mn = (
            rate.min_order_total
            if rate.min_order_total is not None
            else Decimal("0.00")
        )
        mx = rate.max_order_total
        key = (mn, mx)
        if key not in best or rate.price < best[key]:
            best[key] = rate.price
    rows: list[dict] = []
    for (mn, mx), price in sorted(
        best.items(),
        key=lambda kv: (
            kv[0][0],
            kv[0][1] is not None,
            kv[0][1] or Decimal("0.00"),
        ),
    ):
        row = {"min_order": float(mn), "cost": float(price)}
        if mx is not None:
            row["max_order"] = float(mx)
        rows.append(row)
    return rows


def preview_shipping_for_lines(
    *,
    store: Store,
    zone_public_id: str,
    lines: list[dict],
) -> dict:
    """
    Server-side shipping quote for explicit line items and zone.

    Uses PricingEngine (subtotal_after_coupon with no coupon == after bulk)
    as the order subtotal for rate matching, consistent with checkout.
    """
    from django.core.exceptions import ValidationError

    from engine.apps.orders.pricing import PricingEngine

    zone = ShippingZone.objects.filter(
        store=store,
        is_active=True,
        public_id=(zone_public_id or "").strip(),
    ).first()
    if zone is None:
        raise ValidationError({"zone_id": "Unknown or inactive shipping zone."})

    if not lines:
        raise ValidationError({"items": "At least one line item is required."})

    breakdown = PricingEngine.compute(
        store=store,
        lines=lines,
        shipping_zone_id=zone.id,
        shipping_method_id=None,
    )
    return {
        "shipping_cost": str(breakdown.shipping_cost),
        "estimated_days": zone.estimated_delivery_text or "",
        "currency": store.currency,
    }

