import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="supportticketattachment",
            name="file",
            field=models.FileField(
                upload_to=engine.core.media_upload_paths.tenant_support_attachment_upload_to,
            ),
        ),
    ]
