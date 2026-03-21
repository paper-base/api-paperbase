from django.db import migrations

from engine.core.ids import generate_public_id


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")

    rows = [
        {
            "type": "ORDER_RECEIVED",
            "subject": "New order {{ order_number }} — {{ store_name }}",
            "html_body": (
                "<p>You have a new order.</p>"
                "<p><strong>Order:</strong> {{ order_number }}</p>"
                "<p><strong>Store:</strong> {{ store_name }}</p>"
                "<p><strong>Customer:</strong> {{ customer_name }} ({{ customer_email }})</p>"
                "<p><strong>Total:</strong> {{ currency }} {{ total }}</p>"
            ),
            "text_body": (
                "New order {{ order_number }} at {{ store_name }}.\n"
                "Customer: {{ customer_name }} ({{ customer_email }})\n"
                "Total: {{ currency }} {{ total }}\n"
            ),
        },
        {
            "type": "ORDER_CONFIRMED",
            "subject": "Order confirmed — {{ order_number }}",
            "html_body": (
                "<p>Hi {{ customer_name }},</p>"
                "<p>Thank you for your order at <strong>{{ store_name }}</strong>.</p>"
                "<p><strong>Order number:</strong> {{ order_number }}</p>"
                "<p><strong>Total:</strong> {{ currency }} {{ total }}</p>"
            ),
            "text_body": (
                "Hi {{ customer_name }},\n\n"
                "Your order {{ order_number }} at {{ store_name }} is confirmed.\n"
                "Total: {{ currency }} {{ total }}\n"
            ),
        },
        {
            "type": "SUBSCRIPTION_PAYMENT",
            "subject": "Payment receipt — {{ plan_name }}",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Your subscription payment was successful.</p>"
                "<p><strong>Plan:</strong> {{ plan_name }}</p>"
                "<p><strong>Amount:</strong> {{ currency }} {{ amount }}</p>"
                "<p><strong>Payment date:</strong> {{ payment_date }}</p>"
                "<p><strong>Current period ends:</strong> {{ billing_date }}</p>"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Plan: {{ plan_name }}\n"
                "Amount: {{ currency }} {{ amount }}\n"
                "Payment date: {{ payment_date }}\n"
                "Current period ends: {{ billing_date }}\n"
            ),
        },
        {
            "type": "TWO_FA_DISABLE",
            "subject": "Two-factor authentication disabled",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Two-factor authentication was disabled on your account at {{ disabled_at }}.</p>"
                "<p>If you did not do this, secure your account immediately.</p>"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Two-factor authentication was disabled at {{ disabled_at }}.\n"
                "If you did not do this, secure your account immediately.\n"
            ),
        },
        {
            "type": "TWO_FA_CODE",
            "subject": "Your verification code",
            "html_body": (
                "<p>Hi {{ user_name }},</p>"
                "<p>Your verification code is: <strong>{{ code }}</strong></p>"
                "<p>This code expires shortly.</p>"
            ),
            "text_body": (
                "Hi {{ user_name }},\n\n"
                "Your verification code is: {{ code }}\n"
            ),
        },
        {
            "type": "GENERIC_NOTIFICATION",
            "subject": "{{ title }}",
            "html_body": (
                "<p>{{ body }}</p>"
                "{% if action_url %}<p><a href=\"{{ action_url }}\">{{ action_url }}</a></p>{% endif %}"
            ),
            "text_body": "{{ body }}\n{% if action_url %}{{ action_url }}{% endif %}",
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
        type__in=[
            "ORDER_RECEIVED",
            "ORDER_CONFIRMED",
            "SUBSCRIPTION_PAYMENT",
            "TWO_FA_DISABLE",
            "TWO_FA_CODE",
            "GENERIC_NOTIFICATION",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("emails", "0002_seed_auth_templates"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
