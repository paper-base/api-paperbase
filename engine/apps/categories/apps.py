from django.apps import AppConfig


class CategoriesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engine.apps.categories'
    label = 'categories'
    verbose_name = 'Categories'
