from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="review",
            name="store_session_id",
        ),
    ]
