from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0005_alter_category_image_alter_product_image_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["store", "is_active", "status", "display_order"],
                name="product_store_active_status_order_idx",
            ),
        ),
    ]

