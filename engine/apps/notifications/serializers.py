from rest_framework import serializers

from engine.core.serializers import SafeModelSerializer

from .models import PlatformNotification, StorefrontCTA


class NotificationSerializer(SafeModelSerializer):
    """Storefront CTA rows: naming aligned with banners (cta_url, cta_label, start_at/end_at)."""

    is_currently_active = serializers.BooleanField(read_only=True)
    cta_url = serializers.CharField(source="link", read_only=True, allow_null=True, allow_blank=True)
    cta_label = serializers.CharField(source="link_text", read_only=True, allow_blank=True)
    start_at = serializers.SerializerMethodField()
    end_at = serializers.SerializerMethodField()

    class Meta:
        model = StorefrontCTA
        fields = [
            "public_id",
            "cta_text",
            "notification_type",
            "is_active",
            "is_currently_active",
            "cta_url",
            "cta_label",
            "order",
            "start_at",
            "end_at",
            "created_at",
            "updated_at",
        ]

    def get_start_at(self, obj: StorefrontCTA) -> str | None:
        return obj.start_date.isoformat() if obj.start_date else None

    def get_end_at(self, obj: StorefrontCTA) -> str | None:
        return obj.end_date.isoformat() if obj.end_date else None


class ActiveSystemNotificationSerializer(SafeModelSerializer):
    """Read-only global banner payload; never exposes internal PK."""

    class Meta:
        model = PlatformNotification
        fields = ("public_id", "title", "message", "cta_text", "cta_url")
