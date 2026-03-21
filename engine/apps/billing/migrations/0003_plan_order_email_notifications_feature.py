from django.db import migrations


def add_order_email_notifications_feature(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for plan in Plan.objects.filter(name__in=("basic", "premium")):
        features = dict(plan.features or {})
        inner = dict(features.get("features") or {})
        inner["order_email_notifications"] = plan.name == "premium"
        features["features"] = inner
        plan.features = features
        plan.save(update_fields=["features"])


def noop_reverse(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for plan in Plan.objects.filter(name__in=("basic", "premium")):
        features = dict(plan.features or {})
        inner = dict(features.get("features") or {})
        inner.pop("order_email_notifications", None)
        features["features"] = inner
        plan.features = features
        plan.save(update_fields=["features"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_seed_plans"),
    ]

    operations = [
        migrations.RunPython(add_order_email_notifications_feature, noop_reverse),
    ]
