from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0003_customer_denormalized_metrics"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(
                fields=["store", "-created_at"],
                name="customer_store_created_desc_idx",
            ),
        ),
    ]

