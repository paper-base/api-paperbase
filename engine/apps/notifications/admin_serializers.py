from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from .models import StaffNotification, StorefrontCTA


class AdminStaffNotificationSerializer(SafeModelSerializer):
    user_public_id = serializers.CharField(source="user.public_id", read_only=True, allow_null=True)

    class Meta:
        model = StaffNotification
        fields = ['public_id', 'user_public_id', 'message_type', 'title', 'payload', 'is_read', 'created_at']
        read_only_fields = ['public_id', 'user_public_id', 'message_type', 'title', 'payload', 'created_at']


class AdminNotificationSerializer(SafeModelSerializer):
    is_currently_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = StorefrontCTA
        fields = [
            'public_id', 'cta_text', 'notification_type', 'is_active',
            'is_currently_active', 'link', 'link_text',
            'start_date', 'end_date', 'order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['public_id', 'created_at', 'updated_at']
