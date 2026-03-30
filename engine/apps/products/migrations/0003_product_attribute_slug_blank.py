# Generated manually for ProductAttribute.slug blank/default

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_unified_variant_sku"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productattribute",
            name="slug",
            field=models.SlugField(
                blank=True,
                default="",
                help_text="URL slug per store; set only when empty, from name (unique per store).",
                max_length=100,
            ),
        ),
    ]
