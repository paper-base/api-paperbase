import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="store",
            name="logo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=engine.core.media_upload_paths.tenant_store_logo_upload_to,
            ),
        ),
    ]
