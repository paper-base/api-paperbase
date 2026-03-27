from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wishlist", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wishlistitem",
            name="store_session_id",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.RunSQL(
            sql=(
                "UPDATE wishlist_wishlistitem "
                "SET store_session_id = session_key "
                "WHERE store_session_id = '' AND session_key <> '';"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RemoveConstraint(
            model_name="wishlistitem",
            name="unique_session_wishlist_item",
        ),
        migrations.AddConstraint(
            model_name="wishlistitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", True)),
                fields=("store_session_id", "product"),
                name="unique_store_session_wishlist_item",
            ),
        ),
    ]
