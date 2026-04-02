import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=engine.core.media_upload_paths.tenant_category_image_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=engine.core.media_upload_paths.tenant_product_main_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name="productimage",
            name="image",
            field=models.ImageField(
                upload_to=engine.core.media_upload_paths.tenant_product_gallery_upload_to,
            ),
        ),
    ]
