# Generated manually for unified SKU tenant segment

from django.db import migrations, models
from django.utils.text import slugify


def backfill_store_slugs(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    for store in Store.objects.order_by("pk"):
        base_source = (store.name or "").strip()
        base = slugify(base_source)[:100]
        if not base:
            base = f"store-{store.pk}"
        slug = base[:100]
        counter = 2
        original = slug
        while Store.objects.filter(slug=slug).exclude(pk=store.pk).exists():
            suffix = f"-{counter}"
            head_len = max(1, 100 - len(suffix))
            slug = (original[:head_len].rstrip("-") or "s") + suffix
            counter += 1
        Store.objects.filter(pk=store.pk).update(slug=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="slug",
            field=models.SlugField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(backfill_store_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="store",
            name="slug",
            field=models.SlugField(db_index=True, help_text="URL-safe unique slug (globally unique); used as tenant segment in variant SKUs.", max_length=100, unique=True),
        ),
    ]
