from django.apps import AppConfig


class EmailsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.apps.emails"
    label = "emails"
    verbose_name = "Emails"
