# Generated manually for purchase ledger + adjustments

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
        ("customers", "0001_initial"),
        ("stores", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseLedgerEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "public_id",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        help_text="Non-sequential public identifier (e.g. phl_xxx).",
                        max_length=32,
                        unique=True,
                    ),
                ),
                (
                    "customer_public_id",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                ("order_public_id", models.CharField(db_index=True, max_length=32)),
                ("order_number", models.CharField(max_length=20)),
                (
                    "order_uuid",
                    models.UUIDField(blank=True, db_index=True, null=True),
                ),
                (
                    "order_item_public_id",
                    models.CharField(db_index=True, max_length=32, unique=True),
                ),
                (
                    "product_public_id",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "variant_public_id",
                    models.CharField(blank=True, max_length=32, null=True),
                ),
                ("product_name", models.CharField(max_length=255)),
                ("variant_label", models.CharField(blank=True, default="", max_length=255)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("order_status_snapshot", models.CharField(max_length=20)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchase_ledger_entries",
                        to="customers.customer",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchase_ledger_entries",
                        to="orders.order",
                    ),
                ),
                (
                    "order_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchase_ledger_entries",
                        to="orders.orderitem",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_ledger_entries",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="PurchaseLedgerAdjustment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "public_id",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        help_text="Non-sequential public identifier (e.g. pad_xxx).",
                        max_length=32,
                        unique=True,
                    ),
                ),
                (
                    "customer_public_id",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "order_public_id",
                    models.CharField(blank=True, db_index=True, default="", max_length=32),
                ),
                (
                    "order_item_public_id",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "field_key",
                    models.CharField(
                        choices=[
                            ("quantity", "Quantity"),
                            ("unit_price", "Unit price"),
                            ("variant", "Variant"),
                            ("line_removed", "Line removed"),
                            ("line_added", "Line added"),
                        ],
                        max_length=32,
                    ),
                ),
                ("old_value", models.JSONField()),
                ("new_value", models.JSONField()),
                (
                    "reason",
                    models.CharField(default="staff_dashboard_edit", max_length=255),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchase_ledger_adjustments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchase_ledger_adjustments",
                        to="customers.customer",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="purchase_ledger_adjustments",
                        to="orders.order",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_ledger_adjustments",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="purchaseledgerentry",
            index=models.Index(
                fields=["store", "customer", "recorded_at"],
                name="orders_purch_store_i_ledger_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseledgerentry",
            index=models.Index(
                fields=["store", "order_public_id"],
                name="orders_purch_store_o_ledger_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseledgeradjustment",
            index=models.Index(
                fields=["store", "order_public_id", "created_at"],
                name="orders_purch_store_o_adj_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="purchaseledgeradjustment",
            index=models.Index(
                fields=["store", "customer", "created_at"],
                name="orders_purch_store_c_adj_idx",
            ),
        ),
    ]
