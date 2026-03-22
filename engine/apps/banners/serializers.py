from rest_framework import serializers

from .models import Banner


class PublicBannerSerializer(serializers.ModelSerializer):
    """Storefront payload: absolute image URL, no internal keys."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ["public_id", "title", "image", "cta_text", "cta_link", "order"]

    def get_image(self, obj: Banner) -> str | None:
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        if request:
            return request.build_absolute_uri(url)
        return url
