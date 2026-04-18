import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0003_order_payment_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderExportJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("select_all", models.BooleanField(default=False)),
                ("filters", models.JSONField(default=dict)),
                ("selected_order_ids", models.JSONField(blank=True, null=True)),
                ("file_path", models.CharField(blank=True, default="", max_length=512)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="order_export_jobs",
                        to="stores.store",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="order_export_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["store", "status"], name="ordexp_store_status"),
                    models.Index(fields=["expires_at"], name="ordexp_expires"),
                ],
            },
        ),
    ]
