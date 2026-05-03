"""Blog storefront webhook signals."""

from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from engine.apps.stores.tasks import dispatch_storefront_webhook

from .models import Blog


@receiver(post_save, sender=Blog)
def blog_webhook_on_save(sender, instance: Blog, created: bool, **kwargs) -> None:
    sid = instance.store.public_id
    if not sid:
        return
    event = "blog.created" if created else "blog.updated"
    payload: dict[str, Any] = {"event": event, "type": "blog", "store_public_id": sid}
    if instance.slug:
        payload["slug"] = instance.slug
    dispatch_storefront_webhook.delay(sid, payload)


@receiver(post_delete, sender=Blog)
def blog_webhook_on_delete(sender, instance: Blog, **kwargs) -> None:
    sid = instance.store.public_id
    if not sid:
        return
    payload: dict[str, Any] = {"event": "blog.deleted", "type": "blog", "store_public_id": sid}
    if instance.slug:
        payload["slug"] = instance.slug
    dispatch_storefront_webhook.delay(sid, payload)
