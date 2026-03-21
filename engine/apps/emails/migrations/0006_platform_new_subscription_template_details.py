from django.db import migrations


def update_platform_new_subscription_template(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")
    tpl = EmailTemplate.objects.filter(type="PLATFORM_NEW_SUBSCRIPTION").first()
    if not tpl:
        return
    tpl.subject = "[Platform] New subscription — {{ store_name }}"
    tpl.html_body = (
        "<p>New subscription (first activation).</p>"
        "<p><strong>Store name:</strong> {{ store_name }}</p>"
        "<p><strong>Store public_id:</strong> {{ store_public_id }}</p>"
        "<p><strong>Store domain:</strong> {{ store_domain }}</p>"
        "<p><strong>Store owner (record):</strong> {{ store_owner_name_on_record }} "
        "— {{ store_owner_email_on_record }}</p>"
        "<p><strong>Store phone:</strong> {{ store_phone }}</p>"
        "<p><strong>Store contact email:</strong> {{ store_contact_email }}</p>"
        "<p><strong>Store address:</strong> {{ store_address }}</p>"
        "<hr/>"
        "<p><strong>Account user public_id:</strong> {{ user_public_id }}</p>"
        "<p><strong>Account name:</strong> {{ user_full_name }}</p>"
        "<p><strong>Account email:</strong> {{ store_owner_email }}</p>"
        "<p><strong>Plan:</strong> {{ plan_name }}</p>"
        "<p><strong>Status:</strong> {{ subscription_status }}</p>"
        "<p><strong>Source:</strong> {{ subscription_source }}</p>"
        "<p><strong>Time:</strong> {{ timestamp }}</p>"
    )
    tpl.text_body = (
        "New subscription (first activation)\n"
        "Store name: {{ store_name }}\n"
        "Store public_id: {{ store_public_id }}\n"
        "Store domain: {{ store_domain }}\n"
        "Store owner (record): {{ store_owner_name_on_record }} <{{ store_owner_email_on_record }}>\n"
        "Store phone: {{ store_phone }}\n"
        "Store contact email: {{ store_contact_email }}\n"
        "Store address: {{ store_address }}\n"
        "---\n"
        "Account user public_id: {{ user_public_id }}\n"
        "Account name: {{ user_full_name }}\n"
        "Account email: {{ store_owner_email }}\n"
        "Plan: {{ plan_name }}\n"
        "Status: {{ subscription_status }}\n"
        "Source: {{ subscription_source }}\n"
        "Time: {{ timestamp }}\n"
    )
    tpl.save(update_fields=["subject", "html_body", "text_body"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("emails", "0005_seed_subscription_lifecycle_templates"),
    ]

    operations = [
        migrations.RunPython(update_platform_new_subscription_template, noop_reverse),
    ]
