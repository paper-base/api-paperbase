# Stable tenant code for SKU segment (immutable); backfilled from slug once.

import re

from django.db import migrations, models


def backfill_store_codes(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    for store in Store.objects.order_by("pk"):
        raw = re.sub(r"[^A-Za-z0-9]", "", (store.slug or "")).upper()[:10]
        if not raw:
            raw = re.sub(r"[^A-Za-z0-9]", "", store.public_id or "").upper()[:10]
        if not raw:
            raw = "X"
        candidate = raw[:10]
        n = 2
        base = candidate
        while Store.objects.filter(code=candidate).exclude(pk=store.pk).exists():
            suffix = str(n)
            head = max(1, 10 - len(suffix))
            candidate = (base[:head].rstrip() or "X") + suffix
            candidate = candidate[:10]
            n += 1
        Store.objects.filter(pk=store.pk).update(code=candidate)


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0002_store_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="code",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.RunPython(backfill_store_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="store",
            name="code",
            field=models.CharField(
                db_index=True,
                help_text="Stable uppercase alphanumeric tenant code for variant SKUs; set once and never changes.",
                max_length=10,
                unique=True,
            ),
        ),
    ]
