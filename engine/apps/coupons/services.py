from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from engine.apps.coupons.models import Coupon


@dataclass(frozen=True)
class CouponQuote:
    coupon: Coupon
    discount_amount: Decimal


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _resolve_discount_amount(*, coupon: Coupon, subtotal: Decimal) -> Decimal:
    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
        amount = (subtotal * coupon.discount_value) / Decimal("100")
    else:
        amount = coupon.discount_value
    amount = _quantize_money(amount)
    if amount < Decimal("0.00"):
        return Decimal("0.00")
    if amount > subtotal:
        return subtotal
    return amount


def validate_coupon_for_subtotal(*, store, code: str, subtotal: Decimal) -> CouponQuote:
    normalized_code = (code or "").strip()
    if not normalized_code:
        raise ValidationError({"coupon_code": "Coupon code is required."})
    if subtotal <= Decimal("0.00"):
        raise ValidationError({"coupon_code": "Coupon cannot be applied to empty subtotal."})

    coupon = (
        Coupon.objects.filter(
            store=store,
            code__iexact=normalized_code,
            is_active=True,
        )
        .order_by("-created_at")
        .first()
    )
    if coupon is None:
        raise ValidationError({"coupon_code": "Invalid coupon code."})

    now = timezone.now()
    if coupon.valid_from and now < coupon.valid_from:
        raise ValidationError({"coupon_code": "Coupon is not active yet."})
    if coupon.valid_until and now > coupon.valid_until:
        raise ValidationError({"coupon_code": "Coupon has expired."})
    if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
        raise ValidationError({"coupon_code": "Coupon usage limit reached."})
    if coupon.min_order_value is not None and subtotal < coupon.min_order_value:
        raise ValidationError(
            {"coupon_code": f"Minimum order amount is {coupon.min_order_value} for this coupon."}
        )
    discount_amount = _resolve_discount_amount(coupon=coupon, subtotal=subtotal)
    if discount_amount <= Decimal("0.00"):
        raise ValidationError({"coupon_code": "Coupon is not applicable for this order."})

    return CouponQuote(coupon=coupon, discount_amount=discount_amount)


def consume_coupon_usage(*, coupon: Coupon) -> None:
    with transaction.atomic():
        locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
        if locked.max_uses is not None and locked.times_used >= locked.max_uses:
            raise ValidationError({"coupon_code": "Coupon usage limit reached."})
        Coupon.objects.filter(pk=locked.pk).update(times_used=F("times_used") + 1)
