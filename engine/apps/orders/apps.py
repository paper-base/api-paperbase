from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engine.apps.orders'
    label = 'orders'
    verbose_name = 'Orders'
