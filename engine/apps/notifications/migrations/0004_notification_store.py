# Generated manually: store-scope Notification (CTA) rows for multi-tenant isolation.

import django.db.models.deletion
from django.db import migrations, models


def assign_notification_stores(apps, schema_editor):
    """
    Legacy rows had no store. Attach each to the first Store by primary key so the
    column can become non-nullable. If no store exists, drop orphan notifications.
    """
    Notification = apps.get_model("notifications", "Notification")
    Store = apps.get_model("stores", "Store")
    first = Store.objects.order_by("id").first()
    if first:
        Notification.objects.filter(store_id__isnull=True).update(store_id=first.id)
    else:
        Notification.objects.filter(store_id__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_support_ticket_message_type"),
        ("stores", "0010_remove_store_brand_showcase"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="store",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cta_notifications",
                to="stores.store",
            ),
        ),
        migrations.RunPython(assign_notification_stores, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="notification",
            name="store",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cta_notifications",
                to="stores.store",
            ),
        ),
    ]
