from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from engine.apps.customers.models import Customer
from engine.apps.orders.models import Order


class Command(BaseCommand):
    help = (
        "One-time correction: rebuild customers.total_spent from CONFIRMED orders only, "
        "excluding shipping (uses Order.subtotal_after_discount)."
    )

    def handle(self, *args, **options):
        batch_size = 300
        updated = 0
        last_pk = 0
        while True:
            batch_ids = list(
                Customer.objects.filter(pk__gt=last_pk)
                .order_by("pk")
                .values_list("pk", flat=True)[:batch_size]
            )
            if not batch_ids:
                break

            with transaction.atomic():
                customers = list(
                    Customer.objects.select_for_update().filter(pk__in=batch_ids).order_by("pk")
                )
                spent_rows = (
                    Order.objects.filter(
                        customer_id__in=batch_ids,
                        status=Order.Status.CONFIRMED,
                    )
                    .values("customer_id")
                    .annotate(spent=Coalesce(Sum("subtotal_after_discount"), Decimal("0.00")))
                )
                spent_by_customer = {
                    row["customer_id"]: row["spent"] or Decimal("0.00") for row in spent_rows
                }
                for customer in customers:
                    spent = spent_by_customer.get(customer.pk, Decimal("0.00"))
                    if customer.total_spent != spent:
                        customer.total_spent = spent
                        customer.save(update_fields=["total_spent", "updated_at"])
                        updated += 1

            last_pk = batch_ids[-1]

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} customers."))

