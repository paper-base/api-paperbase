# Generated for prepayment_type additive field.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0003_alter_product_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="prepayment_type",
            field=models.CharField(
                choices=[
                    ("none", "No prepayment"),
                    ("delivery_only", "Delivery fee only"),
                    ("full", "Full amount"),
                ],
                db_index=True,
                default="none",
                help_text=(
                    "Whether this product requires prepayment at checkout. "
                    "Applies to all variants."
                ),
                max_length=20,
            ),
        ),
    ]
