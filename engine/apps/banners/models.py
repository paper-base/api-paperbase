from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from engine.apps.stores.models import Store
from engine.core.ids import generate_public_id
from engine.core.media_upload_paths import (
    tenant_banner_gallery_image_upload_to,
    tenant_banner_image_upload_to,
)


class Banner(models.Model):
    """Store-scoped promotional banner for the storefront (image + optional CTA)."""

    PLACEMENT_CHOICES = [
        ("home_top", "Home Top"),
        ("home_mid", "Home Mid"),
        ("home_bottom", "Home Bottom"),
    ]

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier (e.g. ban_xxx).",
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="banners",
    )
    title = models.CharField(max_length=255, blank=True)
    image = models.ImageField(
        upload_to=tenant_banner_image_upload_to,
        blank=True,
        null=True,
        max_length=500,
    )
    cta_text = models.CharField(max_length=255, blank=True)
    cta_link = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    placement_slots = models.JSONField(default=list)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("banner")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title or f"Banner {self.public_id}"

    def clean(self):
        super().clean()
        slots = self.placement_slots
        if not isinstance(slots, list) or len(slots) == 0:
            raise ValidationError({"placement_slots": "At least one placement slot is required"})
        if not all(isinstance(x, str) for x in slots):
            raise ValidationError({"placement_slots": "Invalid placement slot selected"})
        allowed = {k for k, _ in self.PLACEMENT_CHOICES}
        invalid = [p for p in slots if p not in allowed]
        if invalid:
            raise ValidationError({"placement_slots": "Invalid placement slot selected"})

    def get_media_keys(self) -> list[str]:
        keys: list[str] = []
        main = getattr(self.image, "name", "") if self.image else ""
        if main:
            keys.append(main)
        for row in self.images.all():
            k = getattr(row.image, "name", "") if row.image else ""
            if k:
                keys.append(k)
        return list(dict.fromkeys(keys))

    @property
    def is_currently_active(self) -> bool:
        """True when enabled and within optional start_at / end_at window (matches storefront query)."""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_at is not None and now < self.start_at:
            return False
        if self.end_at is not None and now > self.end_at:
            return False
        return True


class BannerImage(models.Model):
    """Additional images for a banner (up to five total including legacy ``Banner.image``)."""

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier (e.g. bni_xxx).",
    )
    banner = models.ForeignKey(
        Banner,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to=tenant_banner_gallery_image_upload_to, max_length=500)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("bannerimage")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"BannerImage {self.public_id} for Banner {self.banner_id}"

    def get_media_keys(self) -> list[str]:
        key = getattr(self.image, "name", "") if self.image else ""
        return [key] if key else []
