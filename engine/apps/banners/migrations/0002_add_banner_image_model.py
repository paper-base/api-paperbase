# Generated manually for BannerImage gallery support

import django.db.models.deletion
import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BannerImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "public_id",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        help_text="Non-sequential public identifier (e.g. bni_xxx).",
                        max_length=32,
                        unique=True,
                    ),
                ),
                (
                    "image",
                    models.ImageField(upload_to=engine.core.media_upload_paths.tenant_banner_gallery_image_upload_to),
                ),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "banner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="banners.banner",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
    ]
