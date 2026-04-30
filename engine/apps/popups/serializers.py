from __future__ import annotations

from rest_framework import serializers

from engine.core.media_urls import absolute_media_url
from engine.core.serializers import SafeModelSerializer

from .models import StorePopup, StorePopupImage


class StorePopupImageSerializer(SafeModelSerializer):
    """Storefront payload: image URL + public_id + carousel order."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = StorePopupImage
        fields = ["public_id", "image_url", "order"]
        read_only_fields = ["public_id", "image_url", "order"]

    def get_image_url(self, obj: StorePopupImage) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))


class StorePopupSerializer(SafeModelSerializer):
    """Storefront/admin payload for an individual popup."""

    images = serializers.SerializerMethodField()

    class Meta:
        model = StorePopup
        fields = [
            "public_id",
            "title",
            "description",
            "button_text",
            "button_link",
            "delay_seconds",
            "show_frequency",
            "show_on_all_pages",
            "is_active",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]

    def get_images(self, obj: StorePopup) -> list[dict]:
        return StorePopupImageSerializer(
            obj.images.all().order_by("order", "id"),
            many=True,
            context=self.context,
        ).data


class StorePopupWriteSerializer(SafeModelSerializer):
    """
    Admin create/update serializer.

    Handles uploading media via presigned R2 keys:
    - `uploaded_image_keys`: list of ImageField keys to append/create.
    - `image_public_ids_to_delete`: JSON-encoded public_id list for images to remove.
    """

    images = serializers.SerializerMethodField()

    uploaded_image_keys = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        write_only=True,
        required=False,
        default=list,
    )
    image_public_ids_to_delete = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        default="",
    )

    class Meta:
        model = StorePopup
        fields = [
            "public_id",
            "title",
            "description",
            "button_text",
            "button_link",
            "delay_seconds",
            "show_frequency",
            "show_on_all_pages",
            "is_active",
            "images",
            "uploaded_image_keys",
            "image_public_ids_to_delete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]

        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
            "button_text": {"required": False, "allow_blank": True},
            "button_link": {"required": False, "allow_blank": True},
        }

    def get_images(self, obj: StorePopup) -> list[dict]:
        return StorePopupImageSerializer(
            obj.images.all().order_by("order", "id"),
            many=True,
            context=self.context,
        ).data

    def validate_uploaded_image_keys(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v or "").strip()]
        raise serializers.ValidationError("Invalid uploaded_image_keys payload.")

    @staticmethod
    def _normalize_delete_public_ids(raw) -> list[str]:
        """
        Accept:
        - [] / "" / None
        - list[str]
        - JSON-encoded list in multipart form-data (banners pattern)
        """

        if raw in (None, "", []):
            return []
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x or "").strip()]
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return []
            try:
                import json

                data = json.loads(s)
            except Exception:
                return []
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x or "").strip()]
            return []
        return []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        uploaded = attrs.get("uploaded_image_keys") or []
        attrs["uploaded_image_keys"] = self.validate_uploaded_image_keys(uploaded)

        # Normalize delete public IDs into an internal key; service uses this.
        raw = attrs.pop("image_public_ids_to_delete", None)
        attrs["_delete_public_ids"] = self._normalize_delete_public_ids(raw)
        return attrs

    def create(self, validated_data):
        from .popup_service import create_popup

        store = validated_data.pop("store", None)
        uploaded_image_keys = validated_data.pop("uploaded_image_keys", [])
        validated_data.pop("_delete_public_ids", None)

        instance = create_popup(
            store=store,
            data={
                **validated_data,
                "uploaded_image_keys": uploaded_image_keys,
            },
        )
        return instance

    def update(self, instance: StorePopup, validated_data):
        from .popup_service import update_popup

        uploaded_image_keys = validated_data.pop("uploaded_image_keys", [])
        delete_public_ids = validated_data.pop("_delete_public_ids", [])

        updated = update_popup(
            store=instance.store,
            public_id=instance.public_id,
            data={
                **validated_data,
                "uploaded_image_keys": uploaded_image_keys,
                "_delete_public_ids": delete_public_ids,
            },
        )
        return updated

