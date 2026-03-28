from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_stockrestorelog_remove_stock_restored"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="pricing_snapshot",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Snapshot of PricingEngine breakdown at checkout (bulk/coupon/shipping composition).",
            ),
        ),
    ]
