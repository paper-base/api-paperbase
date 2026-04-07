from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0002_store_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="storedeletionjob",
            name="delete_at_snapshot",
            field=models.DateTimeField(
                blank=True,
                help_text="Expected hard-delete time when the job was created (scheduled deletion).",
                null=True,
            ),
        ),
    ]
