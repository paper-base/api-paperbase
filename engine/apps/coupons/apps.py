from django.apps import AppConfig


class CouponsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engine.apps.coupons'
    label = 'coupons'
    verbose_name = 'Coupons'
