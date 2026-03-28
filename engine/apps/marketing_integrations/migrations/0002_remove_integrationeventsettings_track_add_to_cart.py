from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("marketing_integrations", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="integrationeventsettings",
            name="track_add_to_cart",
        ),
    ]
