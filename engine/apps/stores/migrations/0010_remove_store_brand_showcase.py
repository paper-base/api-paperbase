from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0009_domain_soft_delete_and_cache"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="store",
            name="brand_showcase",
        ),
    ]
