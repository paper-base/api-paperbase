from django.db import transaction
from django.db.models import F

from engine.apps.customers.models import Customer
from engine.apps.orders.models import Order
from engine.apps.stores.models import Store


def _normalize_phone(phone: str) -> str:
    raw = (phone or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    return digits


def resolve_and_attach_customer(
    order: Order,
    *,
    store: Store,
    name: str,
    phone: str,
    email: str | None,
    address: str | None,
) -> Customer:
    """
    Resolve per-store customer by phone and attach it to the order.
    Identity is strictly (store, phone); email is not used for matching.
    """
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        raise ValueError("phone is required")

    normalized_name = (name or "").strip()
    normalized_email = (email or "").strip() or None
    normalized_address = (address or "").strip() or None

    with transaction.atomic():
        customer, _ = Customer.objects.select_for_update().get_or_create(
            store=store,
            phone=normalized_phone,
            defaults={
                "name": normalized_name,
                "email": normalized_email,
                "address": normalized_address,
            },
        )

        update_fields: list[str] = []
        if normalized_name and not (customer.name or "").strip():
            customer.name = normalized_name
            update_fields.append("name")
        if normalized_email and not (customer.email or "").strip():
            customer.email = normalized_email
            update_fields.append("email")
        if normalized_address and not (customer.address or "").strip():
            customer.address = normalized_address
            update_fields.append("address")
        if update_fields:
            customer.save(update_fields=update_fields)

        if order.customer_id != customer.pk:
            order.customer = customer
            order.save(update_fields=["customer"])

        Customer.objects.filter(pk=customer.pk, store=store).update(total_orders=F("total_orders") + 1)
        customer.refresh_from_db(fields=["total_orders"])
        return customer
