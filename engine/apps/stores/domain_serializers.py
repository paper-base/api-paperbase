import re

from rest_framework import serializers

from .dns_utils import verification_txt_hostname
from .models import Domain
from .services import normalize_domain_host

_HOSTNAME_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)


class DomainSerializer(serializers.ModelSerializer):
    """Read API: never expose internal integer pk."""

    verification_hostname = serializers.SerializerMethodField(read_only=True)
    verification_token = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Domain
        fields = [
            "public_id",
            "domain",
            "is_custom",
            "is_verified",
            "is_primary",
            "is_deleted",
            "deleted_at",
            "verification_token",
            "verification_hostname",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_verification_hostname(self, obj: Domain) -> str | None:
        if not obj.is_custom or obj.is_verified or not obj.verification_token:
            return None
        return verification_txt_hostname(obj.domain)

    def get_verification_token(self, obj: Domain) -> str | None:
        if obj.is_custom and not obj.is_verified and obj.verification_token:
            return obj.verification_token
        return None


class CustomDomainCreateSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=255, write_only=True)

    def validate_domain(self, value: str) -> str:
        norm = normalize_domain_host(value)
        if not norm or "/" in value or " " in norm:
            raise serializers.ValidationError("Enter a valid hostname (no path or spaces).")
        if not _HOSTNAME_RE.match(norm):
            raise serializers.ValidationError("Invalid hostname format.")
        if Domain.objects.filter(domain=norm).exists():
            raise serializers.ValidationError("This domain is already registered.")
        return norm
