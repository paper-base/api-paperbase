# Generated manually — remove storefront session persistence.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0003_storesettings_storefront_public"),
    ]

    operations = [
        migrations.DeleteModel(name="StoreSession"),
    ]
