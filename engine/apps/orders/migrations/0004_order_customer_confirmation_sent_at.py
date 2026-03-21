from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_courier_consignment_id_order_courier_provider_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_confirmation_sent_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Set when ORDER_CONFIRMED was sent to the customer (send-to-courier).",
            ),
        ),
    ]
