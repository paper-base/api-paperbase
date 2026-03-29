# Remove is_legacy_pricing (no longer used)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_alter_order_customer_confirmation_sent_at_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="order",
            name="is_legacy_pricing",
        ),
    ]
