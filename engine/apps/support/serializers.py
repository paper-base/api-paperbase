from rest_framework import serializers

from engine.core.serializers import SafeModelSerializer

from .models import SupportTicket, SupportTicketAttachment


class SupportTicketCreateSerializer(SafeModelSerializer):
    attachments = serializers.ListField(
        child=serializers.FileField(),
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
            "attachments",
        ]

    def create(self, validated_data):
        attachments = validated_data.pop("attachments", [])
        ticket = super().create(validated_data)
        for f in attachments:
            SupportTicketAttachment.objects.create(ticket=ticket, file=f)
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
