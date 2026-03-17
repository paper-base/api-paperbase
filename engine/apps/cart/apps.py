from django.apps import AppConfig


class CartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engine.apps.cart'
    label = 'cart'
    verbose_name = 'Cart'
