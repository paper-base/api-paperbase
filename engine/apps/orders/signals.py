from django.db.models.signals import post_save
from django.dispatch import receiver

from engine.core.realtime import emit_store_event

from .models import Order


@receiver(post_save, sender=Order)
def order_realtime_events(sender, instance, created, **kwargs):
    event = "order.created" if created else "order.updated"
    emit_store_event(
        instance.store.public_id,
        event,
        {"order_public_id": instance.public_id},
    )
