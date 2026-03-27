from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockmovement",
            name="reference_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="source",
            field=models.CharField(
                choices=[
                    ("order", "Order lifecycle"),
                    ("admin", "Admin inventory update"),
                    ("system", "System process"),
                ],
                default="system",
                max_length=20,
            ),
        ),
    ]
