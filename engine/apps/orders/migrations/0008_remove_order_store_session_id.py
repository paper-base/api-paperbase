from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_order_pricing_snapshot"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="order",
            name="store_session_id",
        ),
    ]
