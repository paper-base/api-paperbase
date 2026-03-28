"""Storefront read-only promotion payloads."""

from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import IsStorefrontAPIKey
from engine.apps.coupons.models import BulkDiscount
from engine.apps.products.models import Product
from engine.core.tenancy import require_api_key_store


class BulkDiscountStorefrontListView(APIView):
    """
    Active bulk-discount rules for the tenant (merchandising).

    The pricing engine picks one rule per line by priority; the model has no min_quantity tiers
    (``min_quantity`` is always null in the payload for forward compatibility).
    """

    permission_classes = [IsStorefrontAPIKey]
    authentication_classes = []
    allow_api_key = True

    def get(self, request):
        store = require_api_key_store(request)
        now = timezone.now()
        qs = (
            BulkDiscount.objects.filter(store=store, is_active=True)
            .filter(Q(start_date__isnull=True) | Q(start_date__lte=now))
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
            .select_related("category", "product")
            .order_by("-priority", "-created_at")
        )

        product_filter = (request.query_params.get("product_public_id") or "").strip()
        if product_filter:
            product = (
                Product.objects.filter(
                    public_id=product_filter,
                    store=store,
                    is_active=True,
                    status=Product.Status.ACTIVE,
                )
                .select_related("category", "category__parent")
                .first()
            )
            if not product:
                return Response({"results": []})
            rule_q = Q(target_type=BulkDiscount.TargetType.PRODUCT, product=product) | Q(
                target_type=BulkDiscount.TargetType.SUBCATEGORY,
                category_id=product.category_id,
            )
            parent = getattr(product.category, "parent", None)
            if parent is not None:
                rule_q |= Q(
                    target_type=BulkDiscount.TargetType.CATEGORY,
                    category_id=parent.id,
                )
            qs = qs.filter(rule_q)

        payload = []
        for row in qs:
            payload.append(
                {
                    "public_id": row.public_id,
                    "target_type": row.target_type,
                    "category_public_id": row.category.public_id if row.category_id else None,
                    "product_public_id": row.product.public_id if row.product_id else None,
                    "discount_type": row.discount_type,
                    "discount_value": str(row.discount_value),
                    "priority": row.priority,
                    "start_date": row.start_date.isoformat() if row.start_date else None,
                    "end_date": row.end_date.isoformat() if row.end_date else None,
                    "min_quantity": None,
                }
            )

        return Response({"results": payload})
