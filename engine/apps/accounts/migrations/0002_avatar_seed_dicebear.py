from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="avatar",
        ),
        migrations.AddField(
            model_name="user",
            name="avatar_seed",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional seed for DiceBear avatar URL; empty uses public_id.",
                max_length=128,
            ),
        ),
    ]
