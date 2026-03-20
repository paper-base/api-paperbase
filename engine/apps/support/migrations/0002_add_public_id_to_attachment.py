import uuid

from django.db import migrations, models

from engine.core.ids import generate_public_id


def backfill_public_ids(apps, schema_editor):
    SupportTicketAttachment = apps.get_model("support", "SupportTicketAttachment")
    for obj in SupportTicketAttachment.objects.filter(public_id=""):
        obj.public_id = f"ath_{uuid.uuid4().hex[:20]}"
        obj.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticketattachment",
            name="public_id",
            field=models.CharField(
                db_index=True,
                default="",
                editable=False,
                help_text="Non-sequential public identifier (e.g. ath_xxx).",
                max_length=32,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supportticketattachment",
            name="public_id",
            field=models.CharField(
                db_index=True,
                editable=False,
                help_text="Non-sequential public identifier (e.g. ath_xxx).",
                max_length=32,
                unique=True,
            ),
        ),
    ]
