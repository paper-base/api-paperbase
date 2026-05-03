from django.apps import AppConfig


class BlogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.apps.blogs"
    label = "blogs"
    verbose_name = "Blogs"

    def ready(self) -> None:
        import engine.apps.blogs.signals  # noqa: F401
