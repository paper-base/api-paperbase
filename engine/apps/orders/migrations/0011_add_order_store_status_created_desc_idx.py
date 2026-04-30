from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0010_order_pdf_file_order_pdf_generated_at"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["store", "status", "-created_at"],
                name="orders_store_status_created_desc_idx",
            ),
        ),
    ]

