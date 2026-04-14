from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FraudCheckLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone_number", models.CharField(db_index=True, max_length=32)),
                ("normalized_phone", models.CharField(db_index=True, max_length=16)),
                ("response_json", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("success", "Success"), ("error", "Error")], db_index=True, max_length=16)),
                ("checked_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "store",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fraud_check_logs", to="stores.store"),
                ),
            ],
            options={
                "ordering": ["-checked_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="fraudchecklog",
            index=models.Index(fields=["store", "normalized_phone"], name="fraud_check_store_norm_phone_idx"),
        ),
    ]

