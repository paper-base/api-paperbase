import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stores", "0006_backfill_dedupe_store_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreDeletionOtpChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(db_index=True, editable=False, max_length=32, unique=True)),
                ("code_hash", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deletion_otp_challenges",
                        to="stores.store",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="store_deletion_otp_challenges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={},
        ),
        migrations.AddIndex(
            model_name="storedeletionotpchallenge",
            index=models.Index(fields=["store", "expires_at"], name="stores_stord_store_i_7c8f9a_idx"),
        ),
    ]
