from django.db import migrations, models

import engine.core.media_upload_paths


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_remove_order_orders_store_status_created_desc_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="pdf_file",
            field=models.FileField(
                blank=True,
                max_length=512,
                null=True,
                upload_to=engine.core.media_upload_paths.tenant_order_invoice_upload_to,
            ),
        ),
    ]
