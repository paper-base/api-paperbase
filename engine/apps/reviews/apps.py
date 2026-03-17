from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engine.apps.reviews'
    label = 'reviews'
    verbose_name = 'Reviews'
