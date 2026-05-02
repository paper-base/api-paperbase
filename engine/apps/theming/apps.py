from django.apps import AppConfig


class ThemingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.apps.theming"
    verbose_name = "Theming"

    def ready(self):
        import engine.apps.theming.signals  # noqa: F401
