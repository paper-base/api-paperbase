import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="banner",
            name="image",
            field=models.ImageField(
                upload_to=engine.core.media_upload_paths.tenant_banner_image_upload_to,
            ),
        ),
    ]
