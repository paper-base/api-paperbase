# Allow banners with gallery images only (legacy main image optional).

import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0002_add_banner_image_model"),
    ]

    operations = [
        migrations.AlterField(
            model_name="banner",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=engine.core.media_upload_paths.tenant_banner_image_upload_to,
            ),
        ),
    ]
