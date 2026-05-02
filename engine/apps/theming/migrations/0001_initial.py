import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("stores", "0003_storesettings_language"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorefrontTheme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("palette", models.CharField(choices=[("ivory", "ivory"), ("obsidian", "obsidian"), ("arctic", "arctic"), ("sage", "sage")], default="ivory", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="theme",
                        to="stores.store",
                    ),
                ),
            ],
            options={
                "verbose_name": "Storefront Theme",
            },
        ),
    ]
