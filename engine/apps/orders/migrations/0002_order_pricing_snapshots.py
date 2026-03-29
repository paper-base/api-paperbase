# Generated manually for immutable order pricing snapshots

from decimal import Decimal

from django.db import migrations, models


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def forwards_order_pricing(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    OrderItem = apps.get_model("orders", "OrderItem")
    for oi in OrderItem.objects.all().only("id", "quantity", "price"):
        q = int(oi.quantity)
        unit = _money(Decimal(str(oi.price)))
        ext = _money(unit * q)
        OrderItem.objects.filter(pk=oi.pk).update(
            unit_price=unit,
            original_price=unit,
            discount_amount=Decimal("0.00"),
            line_subtotal=ext,
            line_total=ext,
        )
    for order in Order.objects.all().only("id", "subtotal", "total", "shipping_cost"):
        st = _money(Decimal(str(order.subtotal)))
        Order.objects.filter(pk=order.pk).update(
            subtotal_before_discount=st,
            discount_total=Decimal("0.00"),
            subtotal_after_discount=st,
            is_legacy_pricing=True,
        )
        # Align total with merchandise + shipping when possible
        ship = _money(Decimal(str(order.shipping_cost)))
        new_total = _money(st + ship)
        if _money(Decimal(str(order.total))) != new_total:
            Order.objects.filter(pk=order.pk).update(total=new_total)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="subtotal_before_discount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Sum of line list extended amounts (original_price × qty).",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="discount_total",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Sum of per-line discount × qty.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="subtotal_after_discount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Merchandise total after discounts; equals sum of line_total.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="is_legacy_pricing",
            field=models.BooleanField(
                default=False,
                help_text="True if line financials were backfilled without reliable list-price history.",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="unit_price",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Final charged unit price at order time.",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="original_price",
            field=models.DecimalField(
                decimal_places=2,
                help_text="List/reference unit price frozen at order time.",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Per unit: original_price − unit_price (may be negative for surcharges).",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="line_subtotal",
            field=models.DecimalField(
                decimal_places=2,
                help_text="original_price × quantity",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="line_total",
            field=models.DecimalField(
                decimal_places=2,
                help_text="unit_price × quantity",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.RunPython(forwards_order_pricing, noop_reverse),
        migrations.AlterField(
            model_name="orderitem",
            name="unit_price",
            field=models.DecimalField(
                decimal_places=2,
                help_text="Final charged unit price at order time.",
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="original_price",
            field=models.DecimalField(
                decimal_places=2,
                help_text="List/reference unit price frozen at order time.",
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="line_subtotal",
            field=models.DecimalField(
                decimal_places=2,
                help_text="original_price × quantity",
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="line_total",
            field=models.DecimalField(
                decimal_places=2,
                help_text="unit_price × quantity",
                max_digits=12,
            ),
        ),
        migrations.RemoveField(model_name="order", name="subtotal"),
        migrations.RemoveField(model_name="orderitem", name="price"),
    ]
