from django.db import migrations
from django.utils import timezone


def forwards_fill_published_at(apps, schema_editor):
    Blog = apps.get_model("blogs", "Blog")
    now = timezone.now()
    qs = Blog.objects.filter(published_at__isnull=True)
    for blog in qs.iterator(chunk_size=500):
        fallback = blog.scheduled_at or blog.created_at or now
        Blog.objects.filter(pk=blog.pk).update(published_at=fallback)


class Migration(migrations.Migration):
    dependencies = [
        ("blogs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards_fill_published_at, migrations.RunPython.noop),
        migrations.RemoveIndex(model_name="blog", name="blog_store_status_idx"),
        migrations.RemoveField(model_name="blog", name="scheduled_at"),
        migrations.RemoveField(model_name="blog", name="status"),
    ]
