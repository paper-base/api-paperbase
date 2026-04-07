# Generated manually for one-store-per-owner refactor.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("stores", "0004_rename_stores_stor_status__idx_stores_stor_status_2e6286_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="owner",
            field=models.OneToOneField(
                blank=True,
                help_text="Account that owns this store (at most one store per user).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_store",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
