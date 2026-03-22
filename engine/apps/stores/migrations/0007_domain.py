import secrets
import string

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from engine.core.ids import generate_public_id


def _norm_host(raw: str) -> str:
    if not raw:
        return ""
    x = raw.strip().lower().split(":", 1)[0].strip("/")
    return x.rstrip(".")


def _migrate_domains(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    Domain = apps.get_model("stores", "Domain")
    root = getattr(settings, "PLATFORM_ROOT_DOMAIN", "mybaas.com").lower().strip(".")
    alpha = string.ascii_lowercase + string.digits

    def gen_label():
        n = secrets.randbelow(5) + 8
        return "".join(secrets.choice(alpha) for _ in range(n))

    def pick_unique_host():
        while True:
            host = f"{gen_label()}.{root}"
            if not Domain.objects.filter(domain__iexact=host).exists():
                return host

    for store in Store.objects.all().order_by("id"):
        if store.domain:
            norm = _norm_host(store.domain)
            if norm:
                is_generated = norm.endswith("." + root)
                Domain.objects.create(
                    store_id=store.id,
                    public_id=generate_public_id("domain"),
                    domain=norm,
                    is_custom=not is_generated,
                    is_verified=True,
                    is_primary=True,
                    verification_token=None,
                )

        if not Domain.objects.filter(store_id=store.id, is_custom=False).exists():
            has_primary = Domain.objects.filter(store_id=store.id, is_primary=True).exists()
            Domain.objects.create(
                store_id=store.id,
                public_id=generate_public_id("domain"),
                domain=pick_unique_host(),
                is_custom=False,
                is_verified=True,
                is_primary=not has_primary,
                verification_token=None,
            )


def _clear_domains(apps, schema_editor):
    Domain = apps.get_model("stores", "Domain")
    Domain.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0006_storesettings_order_email_notifications"),
    ]

    operations = [
        migrations.CreateModel(
            name="Domain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "public_id",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        help_text="External identifier (e.g. dom_xxx).",
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("domain", models.CharField(max_length=255, unique=True)),
                ("is_custom", models.BooleanField(default=False)),
                ("is_verified", models.BooleanField(default=False)),
                (
                    "verification_token",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domains",
                        to="stores.store",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="domain",
            index=models.Index(fields=["domain"], name="stores_doma_domain_0b7b1b_idx"),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_custom=True),
                fields=("store",),
                name="one_custom_domain_per_store",
            ),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_custom=False),
                fields=("store",),
                name="one_generated_domain_per_store",
            ),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_primary=True),
                fields=("store",),
                name="one_primary_domain_per_store",
            ),
        ),
        migrations.RunPython(_migrate_domains, _clear_domains),
    ]
