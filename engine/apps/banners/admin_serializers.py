from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from .models import Banner


class AdminBannerSerializer(SafeModelSerializer):
    cta_link = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = Banner
        fields = [
            "public_id",
            "image",
            "title",
            "cta_text",
            "cta_link",
            "is_active",
            "order",
            "start_at",
            "end_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at"]
