import logging
import secrets

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import IsStoreAdmin
from engine.core.domain_resolution_cache import invalidate_domain_cache_for_store
from engine.core.tenancy import get_active_store

from .dns_utils import txt_record_contains_token, verification_txt_hostname
from .domain_serializers import CustomDomainCreateSerializer, DomainSerializer
from .models import Domain
from .services import repromote_generated_domain_primary

audit_log = logging.getLogger("audit.domain")


class DomainViewSet(viewsets.ModelViewSet):
    """
    Per-store domains (generated + optional custom). URLs use public_id only.
    """

    permission_classes = [permissions.IsAuthenticated, IsStoreAdmin]
    serializer_class = DomainSerializer
    lookup_field = "public_id"
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        ctx = get_active_store(self.request)
        if not ctx.store:
            return Domain.objects.none()
        if getattr(self, "action", None) == "restore":
            return Domain.all_objects.filter(store=ctx.store, is_deleted=True).order_by(
                "-deleted_at"
            )
        return Domain.objects.filter(store=ctx.store).order_by("is_custom", "created_at")

    def create(self, request, *args, **kwargs):
        ctx = get_active_store(request)
        if not ctx.store:
            return Response({"detail": "No active store."}, status=status.HTTP_403_FORBIDDEN)
        if Domain.objects.filter(store=ctx.store, is_custom=True).exists():
            return Response(
                {"detail": "A custom domain is already configured for this store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = CustomDomainCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        host = ser.validated_data["domain"]
        token = secrets.token_hex(32)
        try:
            dom = Domain.objects.create(
                store=ctx.store,
                domain=host,
                is_custom=True,
                is_verified=False,
                is_primary=False,
                verification_token=token,
            )
        except IntegrityError:
            return Response(
                {"detail": "This domain is already registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        audit_log.info(
            "domain.create domain_public_id=%s store_public_id=%s hostname=%s",
            dom.public_id,
            ctx.store.public_id,
            dom.domain,
        )
        return Response(DomainSerializer(dom).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_custom:
            return Response(
                {"detail": "Generated subdomain cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        store = instance.store
        with transaction.atomic():
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
            repromote_generated_domain_primary(store)
        audit_log.info(
            "domain.soft_delete domain_public_id=%s store_public_id=%s hostname=%s",
            instance.public_id,
            store.public_id,
            instance.domain,
        )

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, public_id=None):
        dom = self.get_object()
        if not dom.is_deleted:
            return Response(
                {"detail": "Domain is not deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                dom.is_deleted = False
                dom.deleted_at = None
                dom.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        except IntegrityError:
            return Response(
                {"detail": "This hostname is no longer available to restore."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        audit_log.info(
            "domain.restore domain_public_id=%s store_public_id=%s hostname=%s",
            dom.public_id,
            dom.store.public_id,
            dom.domain,
        )
        return Response(DomainSerializer(dom).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, public_id=None):
        dom = self.get_object()
        if not dom.is_custom:
            return Response(
                {"detail": "Only custom domains require verification."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if dom.is_verified:
            return Response(DomainSerializer(dom).data)
        if not dom.verification_token:
            return Response(
                {"detail": "No verification token; remove and re-add the domain."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qname = verification_txt_hostname(dom.domain)
        if not txt_record_contains_token(qname, dom.verification_token):
            return Response(
                {"detail": "TXT record not found or token mismatch."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        other = (
            Domain.objects.filter(domain=dom.domain, is_verified=True)
            .exclude(pk=dom.pk)
            .exists()
        )
        if other:
            return Response(
                {"detail": "This hostname is already verified for another store."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dom.is_verified = True
        dom.save(update_fields=["is_verified", "updated_at"])
        audit_log.info(
            "domain.verify domain_public_id=%s store_public_id=%s hostname=%s",
            dom.public_id,
            dom.store.public_id,
            dom.domain,
        )
        return Response(DomainSerializer(dom).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, public_id=None):
        dom = self.get_object()
        if not dom.is_verified:
            return Response(
                {"detail": "Only verified domains can be set as primary."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            Domain.objects.filter(store=dom.store).update(is_primary=False)
            dom.is_primary = True
            dom.save(update_fields=["is_primary", "updated_at"])
        invalidate_domain_cache_for_store(dom.store)
        audit_log.info(
            "domain.set_primary domain_public_id=%s store_public_id=%s hostname=%s",
            dom.public_id,
            dom.store.public_id,
            dom.domain,
        )
        return Response(DomainSerializer(dom).data)
