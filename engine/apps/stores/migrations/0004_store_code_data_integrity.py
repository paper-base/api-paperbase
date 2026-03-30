# Data integrity: every store must have a non-empty code (deploy safeguard).

from django.db import migrations
from django.db.models import Q


def assert_all_store_codes_valid(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    bad = Store.objects.filter(Q(code__isnull=True) | Q(code=""))
    count = bad.count()
    if count:
        raise ValueError(
            f"Migration aborted: {count} store row(s) have null or empty code. "
            "Fix data before deploying."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0003_store_code"),
    ]

    operations = [
        migrations.RunPython(assert_all_store_codes_valid, migrations.RunPython.noop),
    ]
