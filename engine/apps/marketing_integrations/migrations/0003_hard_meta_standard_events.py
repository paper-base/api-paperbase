from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketing_integrations", "0002_update_event_settings_flags"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="integrationeventsettings",
            name="track_order_created",
        ),
        migrations.RemoveField(
            model_name="integrationeventsettings",
            name="track_checkout_started",
        ),
        migrations.RemoveField(
            model_name="integrationeventsettings",
            name="track_product_detail_view",
        ),
        migrations.RemoveField(
            model_name="integrationeventsettings",
            name="track_support_ticket",
        ),
        migrations.AddField(
            model_name="integrationeventsettings",
            name="track_purchase",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="integrationeventsettings",
            name="track_initiate_checkout",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="integrationeventsettings",
            name="track_view_content",
            field=models.BooleanField(default=False),
        ),
    ]

