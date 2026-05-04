from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("theming", "0004_alter_storefronttheme_palette_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="storefronttheme",
            name="card_variant",
            field=models.CharField(
                choices=[("classic", "classic"), ("shelf", "shelf")],
                default="classic",
                max_length=50,
            ),
        ),
    ]
