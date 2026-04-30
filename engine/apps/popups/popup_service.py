from __future__ import annotations

from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from engine.core.media_deletion_service import schedule_media_deletion_from_keys

from .models import StorePopup, StorePopupImage


def get_popup(store) -> StorePopup | None:
    """
    Fetch the store popup with a "prefer active" rule.
    - If any active popup exists, return the newest active one.
    - Otherwise, return the newest popup for the store (editor-friendly).
    """

    active = (
        StorePopup.objects.filter(store=store, is_active=True)
        .prefetch_related("images")
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if active is not None:
        return active

    return (
        StorePopup.objects.filter(store=store)
        .prefetch_related("images")
        .order_by("-updated_at", "-created_at")
        .first()
    )


def create_popup(store, data: dict) -> StorePopup:
    """
    Create a new popup and up to 3 StorePopupImage rows.

    `data` expects:
    - uploaded_image_keys: list[str] (ImageField names / DB keys from presign)
    - other StorePopup fields as model fields.
    """

    if StorePopup.objects.filter(store=store).exists():
        raise ValidationError({"detail": "A popup already exists for this store."})

    uploaded = list(data.get("uploaded_image_keys") or [])
    if len(uploaded) > 3:
        raise ValidationError({"uploaded_image_keys": "Maximum 3 images per popup."})

    uploaded = [str(k).strip() for k in uploaded if str(k or "").strip()]
    uploaded = uploaded[:3]

    # The parent fields are directly stored on the StorePopup model.
    data = {
        k: v
        for k, v in (data or {}).items()
        if k not in {"uploaded_image_keys", "_delete_public_ids"}
    }
    popup_fields = data.copy()

    popup = StorePopup.objects.create(store=store, **popup_fields)
    for i, key in enumerate(uploaded):
        StorePopupImage.objects.create(popup=popup, image=key, order=i)

    # Reload with prefetch for nested serialization.
    return (
        StorePopup.objects.filter(store=store, public_id=popup.public_id)
        .prefetch_related("images")
        .first()
    )


def update_popup(store, public_id: str, data: dict) -> StorePopup:
    """
    Update popup and its images.

    `data` expects internal keys:
    - uploaded_image_keys: list[str]
    - _delete_public_ids: list[str]
    """

    popup = get_object_or_404(
        StorePopup.objects.prefetch_related("images"), store=store, public_id=public_id
    )

    uploaded = list(data.get("uploaded_image_keys") or [])
    delete_ids = list(data.get("_delete_public_ids") or [])

    uploaded = [str(k).strip() for k in uploaded if str(k or "").strip()]
    delete_ids = [str(pid).strip() for pid in delete_ids if str(pid or "").strip()]

    # Enforce max 3 images after the delete+append operation.
    remaining_count = popup.images.exclude(public_id__in=delete_ids).count()
    after_count = remaining_count + len(uploaded)
    if after_count > 3:
        raise ValidationError(
            {"uploaded_image_keys": "Maximum 3 images per popup (after replacement)."}
        )

    # Delete selected images + schedule their R2 deletions.
    if delete_ids:
        to_delete = popup.images.filter(public_id__in=delete_ids)
        old_keys: list[str] = []
        for img in to_delete:
            k = getattr(img.image, "name", None)
            if k:
                old_keys.append(k)
        to_delete.delete()
        if old_keys:
            schedule_media_deletion_from_keys(old_keys)

    # Append uploaded images with next order index.
    if uploaded:
        mx = popup.images.aggregate(m=Max("order"))["m"]
        next_order = 0 if mx is None else int(mx) + 1
        for i, key in enumerate(uploaded):
            StorePopupImage.objects.create(popup=popup, image=key, order=next_order + i)

    # Update popup fields (ignore internal transfer keys).
    internal_keys = {"uploaded_image_keys", "_delete_public_ids"}
    for k, v in (data or {}).items():
        if k in internal_keys:
            continue
        if hasattr(popup, k):
            setattr(popup, k, v)

    popup.save()

    return (
        StorePopup.objects.filter(store=store, public_id=public_id)
        .prefetch_related("images")
        .first()
    )


def delete_popup(store, public_id: str) -> None:
    popup = get_object_or_404(
        StorePopup.objects.prefetch_related("images"), store=store, public_id=public_id
    )
    keys = popup.get_media_keys()
    if keys:
        schedule_media_deletion_from_keys(keys)
    popup.delete()


def delete_popup_image(store, popup_public_id: str, image_public_id: str) -> None:
    popup = get_object_or_404(
        StorePopup.objects.select_related("store"), store=store, public_id=popup_public_id
    )
    img = get_object_or_404(
        StorePopupImage.objects.select_related("popup"),
        popup=popup,
        public_id=image_public_id,
    )
    key = getattr(img.image, "name", None)
    if key:
        schedule_media_deletion_from_keys([key])
    img.delete()

