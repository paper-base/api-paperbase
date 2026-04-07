import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stores", "0007_storedeletionotpchallenge"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreLifecycleAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_public_id", models.CharField(db_index=True, max_length=32)),
                ("action", models.CharField(choices=[("STORE_REMOVE", "Store remove"), ("STORE_DELETE_OTP_SENT", "Delete OTP sent"), ("STORE_DELETE_SCHEDULED", "Delete scheduled")], db_index=True, max_length=40)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "store",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lifecycle_audit_logs",
                        to="stores.store",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="storelifecycleauditlog",
            index=models.Index(fields=["store_public_id", "-created_at"], name="stores_storeli_store_p_idx"),
        ),
    ]
