from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketing_integrations", "0005_rename_marketing_in_store_i_7d1a11_marketing_i_store_i_3c7fcc_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationeventsettings",
            name="track_add_to_cart",
            field=models.BooleanField(default=True),
        ),
    ]
