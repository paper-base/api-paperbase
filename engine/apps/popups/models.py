from django.core.exceptions import ValidationError
from django.db import models

from engine.apps.stores.models import Store
from engine.core.ids import generate_public_id
from engine.core.media_upload_paths import tenant_popup_image_upload_to


class StorePopup(models.Model):
    """Store-scoped marketing popup (title/text + up to 3 images)."""

    class ShowFrequency(models.TextChoices):
        SESSION = "session", "Once per session"
        DAILY = "daily", "Once per day"
        ALWAYS = "always", "Always"

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier (e.g. pop_xxx).",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="popups",
    )

    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    button_text = models.CharField(max_length=255, blank=True)
    button_link = models.CharField(max_length=500, blank=True)

    delay_seconds = models.PositiveIntegerField(default=5)
    show_frequency = models.CharField(
        max_length=10,
        choices=ShowFrequency.choices,
        default=ShowFrequency.SESSION,
    )
    show_on_all_pages = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["store"],
                name="popups_storepopup_store_unique",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("popup")
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.delay_seconds is None:
            raise ValidationError({"delay_seconds": "Delay is required"})
        if self.delay_seconds < 0:
            raise ValidationError({"delay_seconds": "Delay must be non-negative"})
        if self.button_link:
            # Keep validation minimal (matches many other URL fields in this repo).
            if not str(self.button_link).startswith(("http://", "https://")):
                raise ValidationError({"button_link": "button_link must be a valid URL"})

    def get_media_keys(self) -> list[str]:
        keys: list[str] = []
        for row in self.images.all():
            k = getattr(row.image, "name", "") if row.image else ""
            if k:
                keys.append(k)
        return list(dict.fromkeys(keys))

    def __str__(self) -> str:
        return self.title or f"Popup {self.public_id}"


class StorePopupImage(models.Model):
    """Additional images for a store popup (up to 3)."""

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier (e.g. pim_xxx).",
    )
    popup = models.ForeignKey(
        StorePopup,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to=tenant_popup_image_upload_to, max_length=500)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("popupimage")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"PopupImage {self.public_id} for Popup {self.popup_id}"

