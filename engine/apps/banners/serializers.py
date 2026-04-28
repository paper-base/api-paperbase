from rest_framework import serializers

from engine.core.media_urls import absolute_media_url
from engine.core.serializers import SafeModelSerializer

from .models import Banner


def _storefront_banner_images(obj: Banner, request) -> list[dict]:
    """Ordered, de-duplicated by storage key: gallery rows first, then legacy main if distinct."""
    seen: set[str] = set()
    out: list[dict] = []
    for row in obj.images.all().order_by("order", "id"):
        if not row.image or not getattr(row.image, "name", None):
            continue
        key = row.image.name
        if key in seen:
            continue
        url = absolute_media_url(row.image, request)
        if not url:
            continue
        seen.add(key)
        out.append(
            {"public_id": row.public_id, "image_url": url, "order": row.order}
        )
    if obj.image and getattr(obj.image, "name", None):
        key = obj.image.name
        if key not in seen:
            url = absolute_media_url(obj.image, request)
            if url:
                seen.add(key)
                max_o = max((item["order"] for item in out), default=-1)
                out.append(
                    {
                        "public_id": obj.public_id,
                        "image_url": url,
                        "order": max_o + 1,
                    }
                )
    return out


class PublicBannerSerializer(SafeModelSerializer):
    """Storefront payload: all image URLs (gallery + optional legacy), plus CTA and schedule fields."""

    image_url = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    cta_url = serializers.CharField(source="cta_link", read_only=True, allow_blank=True)
    start_at = serializers.SerializerMethodField()
    end_at = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = [
            "public_id",
            "title",
            "image_url",
            "images",
            "cta_text",
            "cta_url",
            "order",
            "placement_slots",
            "start_at",
            "end_at",
        ]

    def get_images(self, obj: Banner) -> list[dict]:
        request = self.context.get("request")
        return _storefront_banner_images(obj, request)

    def get_image_url(self, obj: Banner) -> str | None:
        items = _storefront_banner_images(obj, self.context.get("request"))
        return items[0]["image_url"] if items else None

    def get_start_at(self, obj: Banner) -> str | None:
        return obj.start_at.isoformat() if obj.start_at else None

    def get_end_at(self, obj: Banner) -> str | None:
        return obj.end_at.isoformat() if obj.end_at else None
