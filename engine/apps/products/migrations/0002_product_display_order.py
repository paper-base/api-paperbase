# Generated manually for display_order + backfill.

from django.db import migrations, models


def backfill_display_order(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    Category = apps.get_model("products", "Category")
    Product = apps.get_model("products", "Product")
    for store in Store.objects.all().iterator():
        for cat in Category.objects.filter(store_id=store.id).iterator():
            prods = list(
                Product.objects.filter(store_id=store.id, category_id=cat.id).order_by(
                    "-created_at", "public_id"
                )
            )
            for i, p in enumerate(prods):
                p.display_order = i
            if prods:
                Product.objects.bulk_update(prods, ["display_order"], batch_size=200)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Sort order within this product's category (scoped per store).",
            ),
        ),
        migrations.RunPython(backfill_display_order, noop_reverse),
    ]
