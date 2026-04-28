from django.db.models import Max
from rest_framework import serializers

from engine.core.media_deletion_service import schedule_media_deletion_from_keys
from engine.core.media_urls import absolute_media_url
from engine.core.serializers import SafeModelSerializer

from .models import Banner, BannerImage


class AdminBannerImageSerializer(SafeModelSerializer):
    """Read-only gallery row for admin banner detail/list."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = BannerImage
        fields = ["public_id", "image_url", "order", "created_at"]
        read_only_fields = ["public_id", "image_url", "order", "created_at"]

    def get_image_url(self, obj: BannerImage) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))


class AdminBannerSerializer(SafeModelSerializer):
    cta_link = serializers.URLField(required=False, allow_blank=True)
    placement_slots = serializers.JSONField()
    is_currently_active = serializers.ReadOnlyField()
    images = AdminBannerImageSerializer(many=True, read_only=True)
    image_key = serializers.CharField(write_only=True, required=False, allow_blank=False)
    uploaded_image_keys = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        write_only=True,
        required=False,
        default=list,
    )
    # Multipart forms send this as a plain string; JSONField can reject some clients.
    image_public_ids_to_delete = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        default="",
    )

    class Meta:
        model = Banner
        fields = [
            "public_id",
            "image",
            "image_key",
            "images",
            "uploaded_image_keys",
            "image_public_ids_to_delete",
            "title",
            "cta_text",
            "cta_link",
            "is_active",
            "is_currently_active",
            "order",
            "placement_slots",
            "start_at",
            "end_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]
        extra_kwargs = {
            "image": {"required": False, "allow_null": True, "read_only": True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        req = self.context.get("request")
        first = instance.images.order_by("order", "id").first()
        if first is not None and first.image and getattr(first.image, "name", None):
            data["image"] = absolute_media_url(first.image, req)
        elif instance.image and getattr(instance.image, "name", None):
            data["image"] = absolute_media_url(instance.image, req)
        else:
            data["image"] = None
        return data

    def validate_placement_slots(self, value):
        # Multipart / FormParser often delivers JSON as a string; model clean() requires a list.
        if isinstance(value, str):
            s = value.strip()
            if not s:
                raise serializers.ValidationError("At least one placement slot is required")
            try:
                import json

                value = json.loads(s)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("Invalid placement_slots JSON") from exc
        if not isinstance(value, list):
            raise serializers.ValidationError("placement_slots must be a list")
        if not value or len(value) == 0:
            raise serializers.ValidationError("At least one placement slot is required")
        if not all(isinstance(x, str) for x in value):
            raise serializers.ValidationError("Invalid placement slot selected")
        allowed = {k for k, _ in Banner.PLACEMENT_CHOICES}
        invalid = [p for p in value if p not in allowed]
        if invalid:
            raise serializers.ValidationError("Invalid placement slot selected")
        return value

    def validate_uploaded_image_keys(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v or "").strip()]
        raise serializers.ValidationError("Invalid uploaded image keys payload.")

    @staticmethod
    def _main_slot_count(instance: Banner | None, validated_data: dict) -> int:
        if "image" in validated_data:
            return 1 if validated_data.get("image") else 0
        if instance is None:
            return 0
        return 1 if (instance.image and getattr(instance.image, "name", None)) else 0

    @staticmethod
    def _gallery_count_after_delete(instance: Banner, delete_public_ids: list[str]) -> int:
        qs = instance.images.all()
        if delete_public_ids:
            qs = qs.exclude(public_id__in=delete_public_ids)
        return qs.count()

    @staticmethod
    def _slots_available(banner: Banner) -> int:
        main = 1 if (banner.image and getattr(banner.image, "name", None)) else 0
        return max(0, 5 - main - banner.images.count())

    def _normalize_delete_public_ids(self, raw) -> list[str]:
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
            except (json.JSONDecodeError, TypeError):
                return []
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x or "").strip()]
        return []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        image_key = attrs.pop("image_key", None)
        if image_key:
            attrs["image"] = image_key
        raw = attrs.pop("image_public_ids_to_delete", None)
        if raw in (None, "") and getattr(self, "initial_data", None) is not None:
            raw = self.initial_data.get("image_public_ids_to_delete")
        attrs["_delete_public_ids"] = self._normalize_delete_public_ids(raw)

        uploaded = list(attrs.get("uploaded_image_keys") or [])
        delete_public_ids = attrs["_delete_public_ids"]

        if self.instance is None:
            main_slots = self._main_slot_count(None, attrs)
            if main_slots + len(uploaded) > 5:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Maximum 5 images per banner (legacy image field + gallery)."]}
                )
            if main_slots + len(uploaded) == 0:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Add at least one banner image."]}
                )
        else:
            gallery_after = self._gallery_count_after_delete(self.instance, delete_public_ids)
            main_after = self._main_slot_count(self.instance, attrs)
            if main_after + gallery_after + len(uploaded) > 5:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Maximum 5 images per banner (legacy image field + gallery)."]}
                )

        return attrs

    def _append_uploaded_gallery(self, banner: Banner, keys: list[str]) -> None:
        slots = self._slots_available(banner)
        use_keys = [str(k).strip() for k in (keys or []) if str(k or "").strip()][:slots]
        if not use_keys:
            return
        mx = banner.images.aggregate(m=Max("order"))["m"]
        next_order = 0 if mx is None else int(mx) + 1
        for i, key in enumerate(use_keys):
            BannerImage.objects.create(banner=banner, image=key, order=next_order + i)

    def create(self, validated_data):
        validated_data.pop("_delete_public_ids", None)
        uploaded_image_keys = validated_data.pop("uploaded_image_keys", None) or []
        instance = super().create(validated_data)
        self._append_uploaded_gallery(instance, uploaded_image_keys)
        return instance

    def update(self, instance, validated_data):
        delete_public_ids = validated_data.pop("_delete_public_ids", [])
        uploaded_image_keys = validated_data.pop("uploaded_image_keys", None) or []

        old_gallery_keys: list[str] = []
        if delete_public_ids:
            qs = instance.images.filter(public_id__in=delete_public_ids)
            for img in qs:
                k = getattr(img.image, "name", None)
                if k:
                    old_gallery_keys.append(k)
            qs.delete()

        old_main_key = (
            instance.image.name
            if instance.image and getattr(instance.image, "name", None)
            else None
        )
        image_provided = "image" in validated_data

        self._append_uploaded_gallery(instance, uploaded_image_keys)

        instance = super().update(instance, validated_data)

        if old_gallery_keys:
            schedule_media_deletion_from_keys(old_gallery_keys)
        if image_provided and old_main_key and old_main_key != getattr(instance.image, "name", ""):
            schedule_media_deletion_from_keys([old_main_key])
        return instance
