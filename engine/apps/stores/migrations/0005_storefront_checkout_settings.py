from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0004_storesettings_storefront_webhook_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorefrontCheckoutSettings",
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
                    "customer_form_variant",
                    models.CharField(
                        choices=[
                            ("minimal", "Minimal"),
                            ("extended", "Extended"),
                        ],
                        default="extended",
                        max_length=20,
                    ),
                ),
                (
                    "store",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checkout_settings",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "verbose_name": "Storefront Checkout Settings",
            },
        ),
    ]
