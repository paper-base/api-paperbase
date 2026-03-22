from django.db import migrations, models


def forwards(apps, schema_editor):
    StaffInboxNotification = apps.get_model("notifications", "StaffInboxNotification")
    StaffInboxNotification.objects.filter(message_type="contact_submission").update(
        message_type="support_ticket"
    )


def backwards(apps, schema_editor):
    StaffInboxNotification = apps.get_model("notifications", "StaffInboxNotification")
    StaffInboxNotification.objects.filter(message_type="support_ticket").update(
        message_type="contact_submission"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_staff_inbox_and_global_system_notification"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="staffinboxnotification",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("new_order", "New order"),
                    ("new_customer", "New customer"),
                    ("low_stock", "Product out of stock"),
                    ("wishlist_add", "Product added to wishlist"),
                    ("support_ticket", "Support ticket submitted"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=30,
            ),
        ),
    ]
