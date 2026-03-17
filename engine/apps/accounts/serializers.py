from django.contrib.auth import get_user_model
from rest_framework import serializers

from engine.apps.stores.models import StoreMembership

User = get_user_model()


class StoreSummarySerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="get_role_display")

    class Meta:
        model = StoreMembership
        fields = ["store_id", "store", "role"]
        extra_kwargs = {
            "store": {"read_only": True},
        }


class MeSerializer(serializers.ModelSerializer):
    stores = serializers.SerializerMethodField()
    active_store_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_staff",
            "is_superuser",
            "active_store_id",
            "stores",
        ]

    def get_active_store_id(self, obj):
        request = self.context.get("request")
        if request and getattr(request, "auth", None):
            return request.auth.get("active_store_id")
        return None

    def get_stores(self, obj):
        memberships = StoreMembership.objects.select_related("store").filter(
            user=obj,
            is_active=True,
        )
        return [
            {
                "id": m.store_id,
                "name": m.store.name,
                "domain": m.store.domain,
                "role": m.get_role_display(),
            }
            for m in memberships
        ]


