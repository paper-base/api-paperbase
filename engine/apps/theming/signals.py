from django.db.models.signals import post_save
from django.dispatch import receiver

from engine.apps.stores.models import Store

from .models import StorefrontTheme
from .presets import DEFAULT_PALETTE


@receiver(post_save, sender=Store)
def create_storefront_theme_for_new_store(sender, instance: Store, created: bool, **kwargs):
    if not created:
        return
    StorefrontTheme.objects.get_or_create(
        store=instance,
        defaults={"palette": DEFAULT_PALETTE},
    )
