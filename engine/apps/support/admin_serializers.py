from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from .models import SupportTicket, SupportTicketAttachment


class AdminSupportTicketAttachmentSerializer(SafeModelSerializer):
    class Meta:
        model = SupportTicketAttachment
        fields = ["public_id", "file", "created_at"]
        read_only_fields = ["public_id", "file", "created_at"]


class AdminSupportTicketSerializer(SafeModelSerializer):
    attachments = AdminSupportTicketAttachmentSerializer(many=True, read_only=True)
    store_public_id = serializers.CharField(source="store.public_id", read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "public_id",
            "store_public_id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "order_number",
            "category",
            "priority",
            "status",
            "internal_notes",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "store_public_id", "created_at", "updated_at", "attachments"]

    def validate_status(self, value):
        # Backward compatibility for older dashboard clients.
        if value == "open":
            return "new"
        return value
