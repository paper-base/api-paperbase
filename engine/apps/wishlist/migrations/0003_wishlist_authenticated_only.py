from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def delete_anonymous_wishlist(apps, schema_editor):
    WishlistItem = apps.get_model("wishlist", "WishlistItem")
    WishlistItem.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("wishlist", "0002_store_session_identity"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="wishlistitem",
            name="unique_store_session_wishlist_item",
        ),
        migrations.RunPython(delete_anonymous_wishlist, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="wishlistitem",
            name="unique_user_wishlist_item",
        ),
        migrations.RemoveField(
            model_name="wishlistitem",
            name="session_key",
        ),
        migrations.RemoveField(
            model_name="wishlistitem",
            name="store_session_id",
        ),
        migrations.AlterField(
            model_name="wishlistitem",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="wishlist_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="wishlistitem",
            constraint=models.UniqueConstraint(
                fields=("user", "product"),
                name="unique_user_wishlist_item",
            ),
        ),
    ]
