from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("marketing_integrations", "0003_hard_meta_standard_events"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app", models.CharField(db_index=True, max_length=50)),
                ("event_type", models.CharField(db_index=True, max_length=80)),
                ("status", models.CharField(choices=[("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")], db_index=True, max_length=20)),
                ("message", models.CharField(blank=True, default="", max_length=500)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_logs", to="stores.store")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="storeeventlog",
            index=models.Index(fields=["store", "created_at"], name="marketing_in_store_i_7d1a11"),
        ),
        migrations.AddIndex(
            model_name="storeeventlog",
            index=models.Index(fields=["store", "event_type", "status"], name="marketing_in_store_i_c0af0f"),
        ),
    ]

