from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blogs", "0004_alter_blog_featured_image"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="blog",
            index=models.Index(
                fields=["store", "is_deleted", "is_public", "-published_at"],
                name="blog_store_deleted_public_published_idx",
            ),
        ),
    ]

