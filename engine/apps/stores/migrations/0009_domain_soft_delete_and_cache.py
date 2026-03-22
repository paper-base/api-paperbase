# Generated manually for soft-delete + partial unique constraints on Domain

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0008_rename_stores_doma_domain_0b7b1b_idx_stores_doma_domain_5e34ee_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="domain",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="domain",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="domain",
            name="one_custom_domain_per_store",
        ),
        migrations.RemoveConstraint(
            model_name="domain",
            name="one_generated_domain_per_store",
        ),
        migrations.RemoveConstraint(
            model_name="domain",
            name="one_primary_domain_per_store",
        ),
        migrations.AlterField(
            model_name="domain",
            name="domain",
            field=models.CharField(max_length=255),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False),
                fields=("domain",),
                name="domain_unique_when_active",
            ),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_custom=True) & models.Q(is_deleted=False),
                fields=("store",),
                name="one_custom_domain_per_store",
            ),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_custom=False) & models.Q(is_deleted=False),
                fields=("store",),
                name="one_generated_domain_per_store",
            ),
        ),
        migrations.AddConstraint(
            model_name="domain",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_primary=True) & models.Q(is_deleted=False),
                fields=("store",),
                name="one_primary_domain_per_store",
            ),
        ),
    ]
