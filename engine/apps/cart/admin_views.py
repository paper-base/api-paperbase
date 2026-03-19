from rest_framework import viewsets, mixins

from config.permissions import IsDashboardUser
from engine.core.tenancy import get_active_store
from .models import Cart
from .admin_serializers import AdminCartSerializer


class AdminCartViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsDashboardUser]
    serializer_class = AdminCartSerializer
    queryset = Cart.objects.select_related('user').prefetch_related(
        'items__product',
    ).all()
    lookup_field = 'public_id'

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        # Cart has no direct store FK; scope via the products in cart items.
        return qs.filter(items__product__store=ctx.store).distinct()
