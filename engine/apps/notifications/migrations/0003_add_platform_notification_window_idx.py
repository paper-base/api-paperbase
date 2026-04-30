from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_storefrontcta_notifications_storefrontcta_store_unique"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="platformnotification",
            index=models.Index(
                fields=["is_active", "start_at", "end_at"],
                name="platformnotif_active_window_idx",
            ),
        ),
    ]

