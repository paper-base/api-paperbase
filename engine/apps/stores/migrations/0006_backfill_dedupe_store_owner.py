"""
Dedupe users who own multiple stores (keep best ACTIVE store by -updated_at),
purge extra stores using the same graph delete as hard_delete_store, then
set Store.owner from OWNER membership and enforce NOT NULL.

Reverse is a no-op (destructive data migration).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards(apps, schema_editor):
    StoreMembership = apps.get_model("stores", "StoreMembership")
    Store = apps.get_model("stores", "Store")

    from collections import defaultdict

    from engine.apps.stores.models import Store as RealStore
    from engine.apps.stores.tasks import _purge_store_graph

    qs = StoreMembership.objects.filter(role="owner", is_active=True).select_related(
        "store"
    )
    by_user = defaultdict(list)
    for m in qs:
        by_user[m.user_id].append(m)

    for _user_id, memberships in by_user.items():
        if len(memberships) <= 1:
            continue
        stores = [m.store for m in memberships]

        def sort_key(s):
            is_active = 0 if getattr(s, "status", None) == "active" else 1
            u = getattr(s, "updated_at", None)
            ts = u.timestamp() if u is not None else 0.0
            return (is_active, -ts, -s.pk)

        stores_sorted = sorted(stores, key=sort_key)
        for dup in stores_sorted[1:]:
            st = RealStore.objects.filter(pk=dup.pk).first()
            if st:
                _purge_store_graph(st, None)

    for store in Store.objects.all():
        m = (
            StoreMembership.objects.filter(
                store_id=store.pk,
                role="owner",
                is_active=True,
            )
            .first()
        )
        if m:
            RealStore.objects.filter(pk=store.pk).update(owner_id=m.user_id)

    for store in Store.objects.all():
        has_owner = StoreMembership.objects.filter(
            store_id=store.pk,
            role="owner",
            is_active=True,
        ).exists()
        if not has_owner:
            st = RealStore.objects.filter(pk=store.pk).first()
            if st:
                _purge_store_graph(st, None)

    for store in Store.objects.all():
        m = (
            StoreMembership.objects.filter(
                store_id=store.pk,
                role="owner",
                is_active=True,
            )
            .first()
        )
        if m:
            RealStore.objects.filter(pk=store.pk).update(owner_id=m.user_id)

    for st in list(RealStore.objects.filter(owner__isnull=True)):
        _purge_store_graph(st, None)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0005_store_owner"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="store",
            name="owner",
            field=models.OneToOneField(
                help_text="Account that owns this store (at most one store per user).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_store",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
