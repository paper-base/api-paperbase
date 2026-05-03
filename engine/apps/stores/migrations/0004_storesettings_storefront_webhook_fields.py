from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0003_storesettings_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="storefront_url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Deployed storefront base URL e.g. store.yourdomain.com. Used for webhook dispatch.",
            ),
        ),
        migrations.AddField(
            model_name="storesettings",
            name="revalidate_secret",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Shared HMAC secret for storefront webhook verification. Must match REVALIDATE_SECRET on the storefront.",
                max_length=64,
            ),
        ),
    ]
