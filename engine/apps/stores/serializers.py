from django.contrib.auth import get_user_model
from rest_framework import serializers
from engine.core.serializers import SafeModelSerializer

from engine.apps.billing.feature_gate import has_feature

from .models import Store, StoreMembership, StoreRestoreChallenge, StoreSettings
from .services import ORDER_EMAIL_NOTIFICATIONS_FEATURE

User = get_user_model()


class StoreSettingsSerializer(SafeModelSerializer):
    class Meta:
        model = StoreSettings
        fields = [
            "modules_enabled",
            "low_stock_threshold",
            "extra_field_schema",
            "email_notify_owner_on_order_received",
            "email_customer_on_order_confirmed",
            "public_api_enabled",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False):
            if not has_feature(request.user, ORDER_EMAIL_NOTIFICATIONS_FEATURE):
                data["email_notify_owner_on_order_received"] = False
                data["email_customer_on_order_confirmed"] = False
        return data

    def validate(self, attrs):
        request = self.context.get("request")
        membership = self.context.get("membership")
        for key in (
            "email_notify_owner_on_order_received",
            "email_customer_on_order_confirmed",
        ):
            if key not in attrs:
                continue
            if (
                not membership
                or membership.role != StoreMembership.Role.OWNER
                or not membership.is_active
            ):
                raise serializers.ValidationError(
                    {key: "Only the store owner can change order email notification settings."}
                )
            if attrs[key] and (
                not request
                or not getattr(request.user, "is_authenticated", False)
                or not has_feature(request.user, ORDER_EMAIL_NOTIFICATIONS_FEATURE)
            ):
                raise serializers.ValidationError(
                    {
                        key: (
                            "This feature (order_email_notifications) is not available on your plan. "
                            "Please upgrade."
                        )
                    }
                )
        return attrs


class StoreSerializer(SafeModelSerializer):
    settings = StoreSettingsSerializer(read_only=True)

    class Meta:
        model = Store
        fields = [
            "public_id",
            "name",
            "store_type",
            "owner_name",
            "owner_email",
            "is_active",
            "status",
            "delete_at",
            "removed_at",
            "currency",
            "created_at",
            "updated_at",
            "settings",
        ]
        read_only_fields = [
            "public_id",
            "created_at",
            "updated_at",
            "settings",
            "status",
            "delete_at",
            "removed_at",
        ]


class RecoverableStoreSerializer(SafeModelSerializer):
    class Meta:
        model = Store
        fields = [
            "public_id",
            "name",
            "status",
            "delete_at",
            "removed_at",
            "delete_requested_at",
        ]
        read_only_fields = fields


class RestoreSendSerializer(serializers.Serializer):
    store_public_id = serializers.CharField(required=True)
    purpose = serializers.ChoiceField(choices=StoreRestoreChallenge.Purpose.choices)


class RestoreVerifySerializer(serializers.Serializer):
    store_public_id = serializers.CharField(required=True)
    challenge_public_id = serializers.CharField(required=True)
    owner_code = serializers.CharField(required=False, allow_blank=True)
    contact_code = serializers.CharField(required=False, allow_blank=True)


class StoreMembershipSerializer(SafeModelSerializer):
    user_public_id = serializers.CharField(source="user.public_id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    store_public_id = serializers.CharField(source="store.public_id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)

    class Meta:
        model = StoreMembership
        fields = [
            "public_id",
            "user_public_id",
            "user_email",
            "store_public_id",
            "store_name",
            "role",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["public_id", "user_public_id", "created_at", "user_email", "store_name", "store_public_id"]


class DeleteStoreOtpRequestSerializer(serializers.Serializer):
    """Step 1: confirm text + identity before sending delete-schedule OTP."""

    account_email = serializers.CharField(required=True, trim_whitespace=False)
    store_name = serializers.CharField(required=True, trim_whitespace=False)
    confirmation_phrase = serializers.CharField(required=True, trim_whitespace=False)

    def validate(self, attrs):
        account_email = attrs["account_email"]
        store_name = attrs["store_name"]
        if not account_email or not account_email.strip():
            raise serializers.ValidationError({"account_email": "account_email is required."})
        if not store_name or not store_name.strip():
            raise serializers.ValidationError({"store_name": "store_name is required."})
        if not attrs.get("confirmation_phrase"):
            raise serializers.ValidationError({"confirmation_phrase": "confirmation_phrase is required."})
        return attrs


class DeleteStoreOtpVerifySerializer(serializers.Serializer):
    """Step 2: OTP to finalize scheduling permanent deletion."""

    challenge_public_id = serializers.CharField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_otp(self, value: str) -> str:
        s = (value or "").strip()
        if len(s) != 6 or not s.isdigit():
            raise serializers.ValidationError("Enter the 6-digit code.")
        return s


class RemoveStoreRequestSerializer(serializers.Serializer):
    """Remove (inactive) store: exact store name + confirmation phrase."""

    store_name = serializers.CharField(required=True, trim_whitespace=False)
    confirmation_phrase = serializers.CharField(required=True, trim_whitespace=False)

    def validate(self, attrs):
        if not attrs.get("store_name") or not attrs["store_name"].strip():
            raise serializers.ValidationError({"store_name": "store_name is required."})
        if not attrs.get("confirmation_phrase"):
            raise serializers.ValidationError({"confirmation_phrase": "confirmation_phrase is required."})
        return attrs

