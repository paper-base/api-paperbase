from django.db import migrations


def backfill_themes(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    StorefrontTheme = apps.get_model("theming", "StorefrontTheme")
    for store in Store.objects.all().iterator():
        StorefrontTheme.objects.get_or_create(store=store, defaults={"palette": "ivory"})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("theming", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_themes, noop_reverse),
    ]
