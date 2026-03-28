from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="storeanalytics",
            name="cart_items_count",
        ),
        migrations.RemoveField(
            model_name="storeanalytics",
            name="wishlist_items_count",
        ),
    ]
