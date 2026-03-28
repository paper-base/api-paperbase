from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0001_initial"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="cartitem",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "variant"),
                condition=models.Q(variant__isnull=False),
                name="uniq_cartitem_cart_variant_when_set",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "product", "size"),
                condition=models.Q(variant__isnull=True),
                name="uniq_cartitem_cart_product_size_no_variant",
            ),
        ),
    ]
