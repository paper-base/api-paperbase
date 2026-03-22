from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0003_alter_banner_placement"),
    ]

    operations = [
        migrations.RenameField(
            model_name="banner",
            old_name="redirect_url",
            new_name="cta_link",
        ),
        migrations.RenameField(
            model_name="banner",
            old_name="start_date",
            new_name="start_at",
        ),
        migrations.RenameField(
            model_name="banner",
            old_name="end_date",
            new_name="end_at",
        ),
        migrations.RenameField(
            model_name="banner",
            old_name="position",
            new_name="order",
        ),
        migrations.RemoveField(
            model_name="banner",
            name="description",
        ),
        migrations.RemoveField(
            model_name="banner",
            name="is_clickable",
        ),
        migrations.RemoveField(
            model_name="banner",
            name="placement",
        ),
        migrations.AlterModelOptions(
            name="banner",
            options={"ordering": ["order", "id"]},
        ),
    ]
