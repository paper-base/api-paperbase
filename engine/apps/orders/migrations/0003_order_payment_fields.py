# Generated for prepayment lifecycle additive fields + extended status choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_flag"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("payment_pending", "Payment pending"),
                    ("confirmed", "Confirmed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("submitted", "Submitted"),
                    ("verified", "Verified"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="none",
                help_text=(
                    "Prepayment submission state for orders that require prepayment."
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="transaction_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Customer-submitted transaction reference for prepayment verification."
                ),
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="payer_number",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Customer-submitted payer phone/account number for prepayment verification."
                ),
                max_length=32,
            ),
        ),
    ]
