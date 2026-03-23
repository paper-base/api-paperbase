from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def backfill_customer_phone_and_name(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    db_alias = schema_editor.connection.alias

    for customer in Customer.objects.using(db_alias).select_related("user").all():
        phone = (customer.phone or "").strip()
        if not phone:
            phone = f"u{customer.user_id}" if customer.user_id else f"c{customer.pk}"

        # Keep only digits for identity consistency.
        normalized_phone = "".join(ch for ch in phone if ch.isdigit()) or phone
        customer.phone = normalized_phone[:20]

        if not (customer.name or "").strip():
            user = getattr(customer, "user", None)
            if user:
                full_name = (getattr(user, "first_name", "") or "").strip()
                last_name = (getattr(user, "last_name", "") or "").strip()
                display_name = f"{full_name} {last_name}".strip() or (getattr(user, "email", "") or "").strip()
                customer.name = display_name[:255]

        customer.save(update_fields=["phone", "name"])


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="address",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="customer",
            name="total_orders",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="customer",
            name="phone",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name="customer",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="customer_profiles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_customer_phone_and_name, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="customer",
            name="uniq_customer_store_user",
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                condition=Q(user__isnull=False),
                fields=("store", "user"),
                name="uniq_customer_store_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                fields=("store", "phone"),
                name="uniq_customer_store_phone",
            ),
        ),
    ]
