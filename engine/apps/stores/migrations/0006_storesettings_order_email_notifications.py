from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0005_storemembership_public_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="email_notify_owner_on_order_received",
            field=models.BooleanField(
                default=False,
                help_text="Premium: send email to store when a new order is placed.",
            ),
        ),
        migrations.AddField(
            model_name="storesettings",
            name="email_customer_on_order_confirmed",
            field=models.BooleanField(
                default=False,
                help_text="Premium: email customer when order is confirmed (send-to-courier).",
            ),
        ),
    ]
