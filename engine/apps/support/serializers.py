from rest_framework import serializers

from engine.core.serializers import SafeModelSerializer

from .models import SupportTicket, SupportTicketAttachment


class SupportTicketCreateSerializer(SafeModelSerializer):
    attachment_keys = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = SupportTicket
        fields = [
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "order_number",
            "category",
            "priority",
            "attachment_keys",
        ]

    def create(self, validated_data):
        attachment_keys = validated_data.pop("attachment_keys", [])
        ticket = super().create(validated_data)
        for key in attachment_keys:
            SupportTicketAttachment.objects.create(ticket=ticket, file=key)
        return ticket


class SupportTicketPublicResponseSerializer(SafeModelSerializer):
    """Echo submitted storefront-safe fields; never internal_notes."""

    class Meta:
        model = SupportTicket
        fields = [
            "public_id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "order_number",
            "category",
            "priority",
            "status",
            "created_at",
            "updated_at",
        ]
