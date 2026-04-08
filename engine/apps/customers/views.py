"""
Customer profile and saved addresses for **authenticated dashboard users** only.

These routes use ``DenyAPIKeyAccess``: Bearer tokens ``ak_pk_`` / ``ak_sk_`` are rejected.
Call them with a **JWT** from ``POST /api/v1/auth/token/`` and resolve the store via
``X-Store-Public-ID`` (or the token's ``active_store_public_id`` claim).

Headless storefront checkout uses the publishable key with ``POST /api/v1/orders/`` and a
stateless line-items payload (no server-side cart or storefront session). Account center
APIs on this module require this separate JWT + store header channel.
"""

from rest_framework.generics import RetrieveAPIView, UpdateAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from config.permissions import DenyAPIKeyAccess, IsDashboardUser
from engine.core.tenancy import get_active_store
from engine.core.tenant_drf import ProvenTenantContextMixin

from .models import Customer, CustomerAddress
from .serializers import CustomerProfileSerializer, CustomerAddressSerializer


def get_or_create_customer(user):
    # For now, resolve the active store lazily from a synthetic request context;
    # views below pass the request explicitly.
    raise RuntimeError("Use get_or_create_customer_for_request instead.")


def get_or_create_customer_for_request(request):
    ctx = get_active_store(request)
    if not ctx.store:
        raise ValidationError("No active store resolved for this request.")
    user = request.user
    if not getattr(user, "is_superuser", False) and not ctx.membership:
        raise PermissionDenied("You do not have access to this store.")
    defaults = {
        "name": (request.user.get_full_name() or "").strip(),
        "email": (getattr(request.user, "email", "") or "").strip() or None,
        "phone": f"u{request.user.pk}",
    }
    customer, _ = Customer.objects.get_or_create(store=ctx.store, user=request.user, defaults=defaults)
    return customer


class CustomerProfileView(ProvenTenantContextMixin, RetrieveAPIView, UpdateAPIView):
    """GET/PATCH /api/v1/customers/me/ - current user's profile."""
    permission_classes = [DenyAPIKeyAccess, IsDashboardUser]
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        return get_or_create_customer_for_request(self.request)


class CustomerAddressListCreateView(ProvenTenantContextMixin, ListCreateAPIView):
    """GET/POST /api/v1/customers/addresses/ - list and create addresses."""
    permission_classes = [DenyAPIKeyAccess, IsDashboardUser]
    serializer_class = CustomerAddressSerializer

    def get_queryset(self):
        customer = get_or_create_customer_for_request(self.request)
        return CustomerAddress.objects.filter(customer=customer)

    def perform_create(self, serializer):
        customer = get_or_create_customer_for_request(self.request)
        serializer.save(customer=customer)


class CustomerAddressDetailView(ProvenTenantContextMixin, RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/v1/customers/addresses/<public_id>/"""
    permission_classes = [DenyAPIKeyAccess, IsDashboardUser]
    serializer_class = CustomerAddressSerializer
    lookup_field = 'public_id'

    def get_queryset(self):
        customer = get_or_create_customer_for_request(self.request)
        return CustomerAddress.objects.filter(customer=customer)
