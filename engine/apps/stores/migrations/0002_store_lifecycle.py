# Generated manually for store lifecycle

import django.db.models.deletion
from django.db import migrations, models


def forwards_store_lifecycle(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    from django.utils import timezone

    now = timezone.now()
    for s in Store.objects.all():
        if s.is_active:
            Store.objects.filter(pk=s.pk).update(
                status="active",
                last_activity_at=getattr(s, "updated_at", None) or now,
                is_active=True,
            )
        else:
            Store.objects.filter(pk=s.pk).update(
                status="pending_delete",
                delete_requested_at=now,
                delete_at=now,
                is_active=False,
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                    ("pending_delete", "Pending delete"),
                ],
                db_index=True,
                default="active",
                help_text="Lifecycle state; is_active is kept in sync for legacy queries.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="removed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="store",
            name="delete_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="store",
            name="delete_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Scheduled permanent deletion time (INACTIVE or PENDING_DELETE).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="last_activity_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Last tenant API activity (ACTIVE stores only).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="inactive_recovery_reminder_sent_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Idempotency: INACTIVE reminder email (7 days before delete_at).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="pending_delete_2d_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="store",
            name="pending_delete_1d_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(forwards_store_lifecycle, noop_reverse),
        migrations.AddIndex(
            model_name="store",
            index=models.Index(fields=["status", "delete_at"], name="stores_stor_status__idx"),
        ),
        migrations.AddIndex(
            model_name="store",
            index=models.Index(
                fields=["status", "last_activity_at"], name="stores_stor_status__2_idx"
            ),
        ),
        migrations.CreateModel(
            name="StoreRestoreChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(db_index=True, editable=False, max_length=32, unique=True)),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("restore_inactive", "Restore inactive"),
                            ("restore_pending_delete", "Restore pending delete"),
                        ],
                        db_index=True,
                        max_length=40,
                    ),
                ),
                ("owner_code_hash", models.CharField(max_length=64)),
                ("contact_code_hash", models.CharField(max_length=64)),
                (
                    "single_channel",
                    models.BooleanField(
                        default=False,
                        help_text="True when owner_email equals contact_email; one code verifies both.",
                    ),
                ),
                ("owner_verified_at", models.DateTimeField(blank=True, null=True)),
                ("contact_verified_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="restore_challenges",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["store", "purpose", "expires_at"], name="stores_stor_store_i_idx")
                ],
            },
        ),
    ]
