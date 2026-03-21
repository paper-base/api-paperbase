from django.db import migrations

from engine.core.ids import generate_public_id


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")

    rows = [
        {
            "type": "EMAIL_VERIFICATION",
            "subject": "Verify your email address",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Please verify your email by visiting:</p>"
                "<p><a href=\"{{ verification_link }}\">{{ verification_link }}</a></p>"
                "<p>This link expires in 3 days.</p>"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Please verify your email by visiting:\n"
                "{{ verification_link }}\n\n"
                "This link expires in 3 days."
            ),
        },
        {
            "type": "PASSWORD_RESET",
            "subject": "Reset your password",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Reset your password by visiting:</p>"
                "<p><a href=\"{{ reset_link }}\">{{ reset_link }}</a></p>"
                "<p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Reset your password by visiting:\n"
                "{{ reset_link }}\n\n"
                "This link expires in 1 hour. If you didn't request this, ignore this email."
            ),
        },
    ]

    for row in rows:
        if EmailTemplate.objects.filter(type=row["type"]).exists():
            continue
        EmailTemplate.objects.create(
            public_id=generate_public_id("emailtemplate"),
            type=row["type"],
            subject=row["subject"],
            html_body=row["html_body"],
            text_body=row["text_body"],
            is_active=True,
        )


def unseed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")
    EmailTemplate.objects.filter(type__in=["EMAIL_VERIFICATION", "PASSWORD_RESET"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("emails", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
