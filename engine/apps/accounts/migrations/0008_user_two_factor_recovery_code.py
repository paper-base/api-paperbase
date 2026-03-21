# Generated manually for 2FA email recovery codes

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_delete_usertwofactorbackupcode"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserTwoFactorRecoveryCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "public_id",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        help_text="Non-sequential public identifier (e.g. tfr_xxx).",
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("code_hash", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="two_factor_recovery_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="usertwofactorrecoverycode",
            index=models.Index(fields=["user", "used_at", "expires_at"], name="accounts_tfr_usr_used_exp"),
        ),
    ]
