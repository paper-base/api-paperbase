from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0003_remove_cartitem_uniq_cartitem_cart_variant_when_set_and_more"),
    ]

    operations = [
        migrations.DeleteModel(name="CartItem"),
        migrations.DeleteModel(name="Cart"),
    ]
