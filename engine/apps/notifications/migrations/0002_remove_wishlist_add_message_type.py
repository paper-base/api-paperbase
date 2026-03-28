from django.db import migrations, models


def forwards(apps, schema_editor):
    StaffNotification = apps.get_model("notifications", "StaffNotification")
    StaffNotification.objects.filter(message_type="wishlist_add").update(message_type="other")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="staffnotification",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("new_order", "New order"),
                    ("new_customer", "New customer"),
                    ("low_stock", "Product out of stock"),
                    ("support_ticket", "Support ticket submitted"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=30,
            ),
        ),
    ]
