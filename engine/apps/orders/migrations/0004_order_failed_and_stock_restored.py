from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_alter_order_discount_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="stock_restored",
            field=models.BooleanField(
                default=False,
                help_text="Whether reserved stock has already been restored for terminal failure/cancel/return states.",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("processing", "Processing"),
                    ("shipped", "Shipped"),
                    ("delivered", "Delivered"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                    ("returned", "Returned"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
    ]
