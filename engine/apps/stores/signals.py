"""Store signals."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Domain, Store
from .services import ensure_generated_store_domain, sync_store_owner_to_user


@receiver(post_save, sender=Store)
def sync_store_owner_on_save(sender, instance, **kwargs):
    """When Store owner_name changes, sync to the owner User."""
    sync_store_owner_to_user(instance)


@receiver(post_save, sender=Store)
def ensure_store_generated_domain(sender, instance, created, **kwargs):
    """Each new store gets exactly one generated subdomain on the platform root domain."""
    if created:
        ensure_generated_store_domain(instance)


@receiver(pre_save, sender=Domain)
def domain_stash_prior_hostname(sender, instance, **kwargs):
    if not instance.pk:
        instance._domain_cache_prior_host = None
        return
    prior = Domain.all_objects.filter(pk=instance.pk).values_list("domain", flat=True).first()
    instance._domain_cache_prior_host = prior


@receiver(post_save, sender=Domain)
def domain_invalidate_resolution_cache(sender, instance, **kwargs):
    from engine.core.domain_resolution_cache import invalidate_domain_host

    invalidate_domain_host(instance.domain)
    old = getattr(instance, "_domain_cache_prior_host", None)
    if old and old != instance.domain:
        invalidate_domain_host(old)


@receiver(post_delete, sender=Domain)
def domain_invalidate_on_hard_delete(sender, instance, **kwargs):
    from engine.core.domain_resolution_cache import invalidate_domain_host

    invalidate_domain_host(instance.domain)
