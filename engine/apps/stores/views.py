from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import viewsets, mixins, permissions, status
from rest_framework.response import Response

from config.permissions import IsPlatformRequest, IsStoreAdmin, IsStoreStaff
from engine.core.tenancy import get_active_store

from .models import Store, StoreMembership, StoreSettings
from .serializers import StoreSerializer, StoreMembershipSerializer, StoreSettingsSerializer

User = get_user_model()


class StoreViewSet(viewsets.ModelViewSet):
    """
    Platform onboarding + store details.

    - On PLATFORM_HOSTS: list/create stores for the authenticated user.
    - On TENANT hosts (or when active store is set): retrieve/update the current store.
    """

    serializer_class = StoreSerializer
    queryset = Store.objects.all()

    def get_permissions(self):
        if self.action in {"list", "create"}:
            return [permissions.IsAuthenticated(), IsPlatformRequest()]
        return [permissions.IsAuthenticated(), IsStoreAdmin()]

    def get_queryset(self):
        if self.action == "list":
            return Store.objects.filter(
                memberships__user=self.request.user,
                memberships__is_active=True,
            ).distinct()

        ctx = get_active_store(self.request)
        if not ctx.store:
            return Store.objects.none()
        return Store.objects.filter(id=ctx.store.id)

    def create(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name is required."}, status=status.HTTP_400_BAD_REQUEST)

        requested_domain = (request.data.get("domain") or "").strip().lower()
        if requested_domain:
            domain = requested_domain
        else:
            slug = slugify(name)[:50].strip("-")
            if not slug:
                slug = "store"
            domain = f"{slug}.{getattr(settings, 'PLATFORM_ROOT_DOMAIN', 'yourplatform.com')}"

        if Store.objects.filter(domain__iexact=domain).exists():
            return Response({"detail": "domain is already in use."}, status=status.HTTP_400_BAD_REQUEST)

        store = Store.objects.create(
            name=name,
            domain=domain,
            timezone=(request.data.get("timezone") or "UTC").strip()[:64],
            currency=(request.data.get("currency") or "USD").strip()[:8],
        )
        StoreSettings.objects.get_or_create(store=store)
        StoreMembership.objects.create(
            user=request.user,
            store=store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )

        return Response(StoreSerializer(store).data, status=status.HTTP_201_CREATED)


class StoreMembershipViewSet(viewsets.ModelViewSet):
    """
    Manage memberships for the active store.
    """

    permission_classes = [permissions.IsAuthenticated, IsStoreAdmin]
    serializer_class = StoreMembershipSerializer

    def get_queryset(self):
        ctx = get_active_store(self.request)
        if not ctx.store:
            return StoreMembership.objects.none()
        return StoreMembership.objects.select_related("user", "store").filter(store=ctx.store)

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        serializer.save(store=ctx.store)


class StoreSettingsViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    View/update settings for the active store.
    """

    permission_classes = [permissions.IsAuthenticated, IsStoreStaff]
    serializer_class = StoreSettingsSerializer

    def get_object(self):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise permissions.PermissionDenied("No active store.")
        settings_obj, _ = StoreSettings.objects.get_or_create(store=store)
        return settings_obj

