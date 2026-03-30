# Unified variant SKU: store FK, per-store unique SKU, remove Product.sku

import re
import secrets
import time

import django.db.models.deletion
from django.db import migrations, models


def backfill_variant_store(apps, schema_editor):
    ProductVariant = apps.get_model("products", "ProductVariant")
    Product = apps.get_model("products", "Product")
    for v in ProductVariant.objects.iterator():
        sid = Product.objects.filter(pk=v.product_id).values_list("store_id", flat=True).first()
        if sid:
            ProductVariant.objects.filter(pk=v.pk).update(store_id=sid)


def _tenant_short(store):
    raw = (getattr(store, "slug", None) or "").strip()
    s = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if not s and getattr(store, "public_id", None):
        s = re.sub(r"[^A-Za-z0-9]", "", store.public_id).upper()
    return (s or "X")[:10]


def regenerate_variant_skus(apps, schema_editor):
    ProductVariant = apps.get_model("products", "ProductVariant")
    Store = apps.get_model("stores", "Store")
    max_retries = 8
    rnd_min = 1_000
    rnd_max = 999_999
    for v in ProductVariant.objects.order_by("pk").iterator():
        store = Store.objects.get(pk=v.store_id)
        tenant = _tenant_short(store)
        ts = int(time.time())
        new_sku = None
        for _ in range(max_retries):
            rnd = secrets.randbelow(rnd_max - rnd_min + 1) + rnd_min
            candidate = f"SKU-{tenant}-{ts}-{rnd}"
            if not ProductVariant.objects.filter(store_id=v.store_id, sku=candidate).exclude(pk=v.pk).exists():
                new_sku = candidate
                break
        if not new_sku:
            raise RuntimeError("SKU generation failed after max retries during migration")
        ProductVariant.objects.filter(pk=v.pk).update(sku=new_sku)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
        ("stores", "0002_store_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="store",
            field=models.ForeignKey(
                help_text="Denormalized from product.store for per-store SKU uniqueness.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="product_variants",
                to="stores.store",
            ),
        ),
        migrations.RunPython(backfill_variant_store, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="productvariant",
            name="uniq_variant_product_sku",
        ),
        migrations.RunPython(regenerate_variant_skus, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="product",
            name="sku",
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="store",
            field=models.ForeignKey(
                help_text="Denormalized from product.store for per-store SKU uniqueness.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="product_variants",
                to="stores.store",
            ),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="sku",
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(fields=("store", "sku"), name="uniq_variant_store_sku"),
        ),
    ]
