from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0002_add_started_at_and_already_missing_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="storesettings",
            name="language",
            field=models.CharField(
                default="en",
                help_text="Preferred storefront language code (e.g. en, bn).",
                max_length=8,
            ),
        ),
    ]
