from django.db import migrations

from engine.core.ids import generate_public_id


def seed_template(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")

    if EmailTemplate.objects.filter(type="TWO_FA_RECOVERY").exists():
        return

    EmailTemplate.objects.create(
        public_id=generate_public_id("emailtemplate"),
        type="TWO_FA_RECOVERY",
        subject="Your 2FA recovery code",
        html_body=(
            "<p>Hi {{ user_name }},</p>"
            "<p>Your recovery code is: <strong>{{ code }}</strong></p>"
            "<p>This code expires at {{ expires_at }}.</p>"
            "<p>If you did not request this, secure your account immediately.</p>"
        ),
        text_body=(
            "Hi {{ user_name }},\n\n"
            "Your recovery code is: {{ code }}\n"
            "Expires at: {{ expires_at }}\n\n"
            "If you did not request this, secure your account immediately.\n"
        ),
        is_active=True,
    )


def unseed_template(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")
    EmailTemplate.objects.filter(type="TWO_FA_RECOVERY").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("emails", "0003_seed_transactional_templates"),
    ]

    operations = [
        migrations.RunPython(seed_template, unseed_template),
    ]
