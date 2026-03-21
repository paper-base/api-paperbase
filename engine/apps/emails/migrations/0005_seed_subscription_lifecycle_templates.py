from django.db import migrations

from engine.core.ids import generate_public_id


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")

    rows = [
        {
            "type": "SUBSCRIPTION_ACTIVATED",
            "subject": "Subscription active — {{ plan_name }}",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Your subscription is now active.</p>"
                "<p><strong>Plan:</strong> {{ plan_name }}</p>"
                "<p><strong>Billing cycle:</strong> {{ billing_cycle }}</p>"
                "<p><strong>Period:</strong> {{ start_date }} → {{ end_date }}</p>"
                "<p><strong>Status:</strong> {{ subscription_status }}</p>"
                "{% if not payment_receipt_sent_separately %}"
                "<p><strong>Amount:</strong> {{ currency }} {{ amount }}</p>"
                "{% endif %}"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Your subscription is active.\n"
                "Plan: {{ plan_name }}\n"
                "Billing cycle: {{ billing_cycle }}\n"
                "Period: {{ start_date }} to {{ end_date }}\n"
                "Status: {{ subscription_status }}\n"
            ),
        },
        {
            "type": "SUBSCRIPTION_CHANGED",
            "subject": "Subscription updated — {{ new_plan_name }}",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Your subscription was updated by an administrator.</p>"
                "<p><strong>Previous plan:</strong> {{ old_plan_name }}</p>"
                "<p><strong>New plan:</strong> {{ new_plan_name }}</p>"
                "<p><strong>Effective:</strong> {{ effective_date }}</p>"
                "<p><strong>Reason:</strong> {{ change_reason }}</p>"
                "<p><strong>Current period ends:</strong> {{ end_date }}</p>"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Your subscription was updated.\n"
                "Previous plan: {{ old_plan_name }}\n"
                "New plan: {{ new_plan_name }}\n"
                "Effective: {{ effective_date }}\n"
                "Reason: {{ change_reason }}\n"
            ),
        },
        {
            "type": "PLATFORM_NEW_SUBSCRIPTION",
            "subject": "[Platform] New subscription — {{ store_name }}",
            "html_body": (
                "<p>New subscription event.</p>"
                "<p><strong>Store:</strong> {{ store_name }}</p>"
                "<p><strong>Owner email:</strong> {{ store_owner_email }}</p>"
                "<p><strong>Plan:</strong> {{ plan_name }}</p>"
                "<p><strong>Status:</strong> {{ subscription_status }}</p>"
                "<p><strong>Source:</strong> {{ subscription_source }}</p>"
                "<p><strong>Time:</strong> {{ timestamp }}</p>"
            ),
            "text_body": (
                "New subscription\n"
                "Store: {{ store_name }}\n"
                "Owner: {{ store_owner_email }}\n"
                "Plan: {{ plan_name }}\n"
                "Status: {{ subscription_status }}\n"
                "Source: {{ subscription_source }}\n"
                "Time: {{ timestamp }}\n"
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
    EmailTemplate.objects.filter(
        type__in=["SUBSCRIPTION_ACTIVATED", "SUBSCRIPTION_CHANGED", "PLATFORM_NEW_SUBSCRIPTION"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("emails", "0004_seed_two_fa_recovery_template"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
