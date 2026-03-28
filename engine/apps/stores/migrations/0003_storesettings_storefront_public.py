from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0002_storeapikey_key_type_scopes"),
    ]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="storefront_public",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Public storefront-only data: theme_settings, country, seo, policy_urls, etc.",
            ),
        ),
    ]
