from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="shippingzone",
            name="estimated_delivery_text",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Customer-facing delivery estimate (e.g. "1-2" days).',
                max_length=64,
            ),
        ),
    ]
