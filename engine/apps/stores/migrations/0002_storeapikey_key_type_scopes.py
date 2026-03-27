from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="storeapikey",
            name="key_type",
            field=models.CharField(
                choices=[("public", "Public"), ("secret", "Secret")],
                db_index=True,
                default="public",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="storeapikey",
            name="scopes",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
