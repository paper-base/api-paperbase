import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stores", "0001_initial"),
        ("orders", "0005_alter_orderstatushistory_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockRestoreLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("cancelled", "Cancelled"),
                            ("failed", "Failed"),
                            ("returned", "Returned"),
                        ],
                        max_length=20,
                    ),
                ),
                ("quantity", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_restore_logs",
                        to="orders.order",
                    ),
                ),
                (
                    "order_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_restore_logs",
                        to="orders.orderitem",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_restore_logs",
                        to="stores.store",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="stockrestorelog",
            constraint=models.UniqueConstraint(
                fields=("order", "order_item", "reason"),
                name="uniq_order_item_restore_reason",
            ),
        ),
        migrations.RemoveField(
            model_name="order",
            name="stock_restored",
        ),
    ]
