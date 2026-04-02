# Generated manually for TrashItem

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrashItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entity_type", models.CharField(choices=[("product", "Product"), ("order", "Order")], db_index=True, max_length=20)),
                ("entity_id", models.CharField(db_index=True, help_text="Internal UUID of the deleted Product or Order.", max_length=36)),
                (
                    "entity_public_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Optional copy of entity public_id for debugging.",
                        max_length=32,
                    ),
                ),
                ("snapshot_json", models.JSONField(help_text="Versioned snapshot for restore.")),
                ("deleted_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("is_restored", models.BooleanField(db_index=True, default=False)),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trash_items_deleted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trash_items",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "ordering": ["-deleted_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="trashitem",
            index=models.Index(fields=["store", "expires_at", "is_restored"], name="core_trashi_store_i_7a8b2c_idx"),
        ),
        migrations.AddIndex(
            model_name="trashitem",
            index=models.Index(fields=["store", "entity_type", "-deleted_at"], name="core_trashi_store_i_9d0e1f_idx"),
        ),
    ]
