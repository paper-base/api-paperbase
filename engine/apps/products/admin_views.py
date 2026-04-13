from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.db.models import Q
from django.utils.text import slugify
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from config.permissions import DenyAPIKeyAccess, IsPlatformSuperuserOrStoreAdmin
from engine.core.activity import log_activity
from engine.core.admin_views import StoreRolePermissionMixin
from engine.core.media_deletion_service import schedule_media_deletion
from engine.core.models import ActivityLog
from engine.core.query_params import include_inactive_truthy
from engine.core.tenancy import assert_instance_belongs_to_store, get_active_store
from engine.apps.inventory.models import Inventory
from engine.apps.inventory.utils import clamp_stock
from .models import (
    Category,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductImage,
    ProductVariant,
)
from .admin_serializers import (
    AdminCategorySerializer,
    AdminProductAttributeSerializer,
    AdminProductAttributeValueSerializer,
    AdminProductImageSerializer,
    AdminProductListSerializer,
    AdminProductSerializer,
    AdminProductVariantSerializer,
)
from .category_tree import descendant_public_ids_including_self
from .product_search import filter_products_by_prioritized_search
from .services import (
    assert_product_creation_allowed,
    build_admin_category_tree,
    invalidate_category_cache,
    invalidate_product_cache,
)


class AdminProductViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = (
        Product.objects.select_related("category")
        .prefetch_related("images")
        .annotate(
            _admin_variant_total=Count("variants", distinct=False),
            _admin_variant_count=Count("variants", filter=Q(variants__is_active=True), distinct=False),
            _admin_variant_stock_sum=Sum(
                "variants__inventory__quantity", filter=Q(variants__is_active=True)
            ),
        )
        .all()
    )
    lookup_field = 'public_id'

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(store=ctx.store).order_by("display_order", "name")

        status_value = (self.request.query_params.get("status") or "").strip().lower()
        if status_value == "active":
            qs = qs.filter(is_active=True)
        elif status_value == "inactive":
            qs = qs.filter(is_active=False)

        stock_filter = (self.request.query_params.get("stock") or "").strip().lower()
        if stock_filter == "in_stock":
            qs = qs.filter(
                Q(_admin_variant_total=0, stock__gt=0)
                | Q(_admin_variant_total__gt=0, _admin_variant_stock_sum__gt=0)
            )
        elif stock_filter == "out_of_stock":
            qs = qs.filter(
                Q(_admin_variant_total=0, stock=0)
                | (
                    Q(_admin_variant_total__gt=0)
                    & (
                        Q(_admin_variant_stock_sum__isnull=True)
                        | Q(_admin_variant_stock_sum__lte=0)
                    )
                )
            )
        elif stock_filter == "low_stock":
            qs = qs.filter(
                Q(_admin_variant_total=0, stock__gt=0, stock__lte=5)
                | Q(
                    _admin_variant_total__gt=0,
                    _admin_variant_stock_sum__gt=0,
                    _admin_variant_stock_sum__lte=5,
                )
            )

        category_public_id = (self.request.query_params.get("category") or "").strip()
        if category_public_id:
            cat = Category.objects.filter(
                store=ctx.store, public_id=category_public_id
            ).first()
            if cat:
                pids = descendant_public_ids_including_self(
                    store_id=ctx.store.id, root_pk=cat.pk
                )
                qs = qs.filter(category__public_id__in=pids)
            else:
                qs = qs.none()

        try:
            if "price_min" in self.request.query_params:
                price_min = Decimal((self.request.query_params.get("price_min") or "").strip())
                qs = qs.filter(price__gte=price_min)
            if "price_max" in self.request.query_params:
                price_max = Decimal((self.request.query_params.get("price_max") or "").strip())
                qs = qs.filter(price__lte=price_max)
        except (InvalidOperation, ValueError):
            pass

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = filter_products_by_prioritized_search(qs, search).distinct()

        ordering = (self.request.query_params.get("ordering") or "newest").strip().lower()
        if ordering == "price_asc":
            return qs.order_by("price", "display_order", "name")
        if ordering == "price_desc":
            return qs.order_by("-price", "display_order", "name")
        if ordering == "popularity":
            return qs.annotate(_order_count=Count("orderitem")).order_by(
                "-_order_count", "display_order", "name"
            )
        return qs.order_by("display_order", "name")

    def get_serializer_class(self):
        if self.action == 'list':
            return AdminProductListSerializer
        return AdminProductSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [DenyAPIKeyAccess(), IsPlatformSuperuserOrStoreAdmin()]
        return super().get_permissions()

    def get_serializer_context(self):
        ctx = get_active_store(self.request)
        return {
            **super().get_serializer_context(),
            "store_id": ctx.store.pk if ctx.store else None,
        }

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError(
                {
                    "detail": (
                        "No active store resolved. Re-login, switch store, or send the "
                        "X-Store-ID header."
                    )
                }
            )
        assert_product_creation_allowed(self.request.user, store)
        instance = serializer.save(store=store)
        mx = (
            Product.objects.filter(store=store, category=instance.category)
            .exclude(pk=instance.pk)
            .aggregate(m=Max("display_order"))["m"]
        )
        instance.display_order = 0 if mx is None else int(mx) + 1
        instance.save(update_fields=["display_order"])
        Inventory.objects.get_or_create(
            product=instance,
            variant=None,
            defaults={"quantity": clamp_stock(0)},
        )
        invalidate_product_cache(store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="product",
            entity_id=instance.public_id,
            summary=f"Product created: {instance.name}",
        )

    def perform_update(self, serializer):
        ctx = get_active_store(self.request)
        assert_instance_belongs_to_store(serializer.instance, ctx.store)
        instance = serializer.save()
        if ctx.store:
            invalidate_product_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="product",
            entity_id=instance.public_id,
            summary=f"Product updated: {instance.name}",
        )

    def perform_destroy(self, instance):
        ctx = get_active_store(self.request)
        user = self.request.user
        if not getattr(user, "is_superuser", False):
            if not ctx.store or instance.store_id != ctx.store.id:
                raise PermissionDenied(
                    detail="You do not have permission to delete this product."
                )
        name = getattr(instance, "name", "")
        public_id = instance.public_id
        store_public_id = instance.store.public_id
        if getattr(user, "is_superuser", False):
            from engine.core.trash_service import hard_delete_product_for_admin

            hard_delete_product_for_admin(product=instance)
        else:
            from engine.core.trash_service import soft_delete_product

            if not ctx.store:
                raise PermissionDenied(
                    detail="You do not have permission to delete this product."
                )
            soft_delete_product(product=instance, store=ctx.store, deleted_by=user)
        invalidate_product_cache(store_public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="product",
            entity_id=public_id,
            summary=f"Product deleted: {name}" if name else "Product deleted",
        )

    @action(detail=False, methods=['get'], url_path='check-slug')
    def check_slug(self, request):
        """Return { available: true } if no product has the given slug in this store."""
        raw = request.query_params.get('slug', '').strip()
        if not raw:
            return Response({'available': True})
        normalized = slugify(raw)
        if not normalized:
            return Response({'available': True})
        ctx = get_active_store(request)
        if not ctx.store:
            return Response({'available': True})
        qs = Product.objects.filter(store=ctx.store)
        exclude_public_id = (request.query_params.get('exclude_public_id') or '').strip()
        if exclude_public_id:
            qs = qs.exclude(public_id=exclude_public_id)
        exists = qs.filter(slug=normalized).exists()
        return Response({'available': not exists})

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """Set ``display_order`` for all products in a category; body must list every product ID once."""
        ctx = get_active_store(request)
        store = ctx.store
        if not store:
            raise ValidationError(
                {
                    "detail": (
                        "No active store resolved. Re-login, switch store, or send the "
                        "X-Store-ID header."
                    )
                }
            )
        cat_pid = (request.data.get("category_public_id") or "").strip()
        ids = request.data.get("product_public_ids")
        if not cat_pid:
            raise ValidationError({"category_public_id": "This field is required."})
        if not isinstance(ids, list):
            raise ValidationError({"product_public_ids": "Expected a list of public IDs."})
        category = Category.objects.filter(store=store, public_id=cat_pid).first()
        if not category:
            raise ValidationError(
                {"category_public_id": "Category not found for this store."}
            )
        expected_qs = Product.objects.filter(store=store, category=category)
        n = expected_qs.count()
        if len(ids) != n or len(set(ids)) != n:
            raise ValidationError(
                {
                    "product_public_ids": (
                        "Must list each product in this category exactly once, with no duplicates."
                    )
                }
            )
        if n == 0:
            return Response({"detail": "ok", "updated": 0})
        existing = set(expected_qs.values_list("public_id", flat=True))
        if set(ids) != existing:
            raise ValidationError(
                {
                    "product_public_ids": (
                        "Product set does not match all products in this category."
                    )
                }
            )
        with transaction.atomic():
            locked = list(
                Product.objects.select_for_update()
                .filter(store=store, category=category, public_id__in=ids)
            )
            if len(locked) != n:
                raise ValidationError(
                    {"product_public_ids": "Could not resolve products for reorder."}
                )
            order_map = {pid: i for i, pid in enumerate(ids)}
            for p in locked:
                p.display_order = order_map[p.public_id]
            Product.objects.bulk_update(locked, ["display_order"])
        invalidate_product_cache(store.public_id)
        return Response({"detail": "ok", "updated": n})


class AdminProductImageViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = AdminProductImageSerializer
    queryset = ProductImage.objects.select_related('product').all()
    lookup_field = 'public_id'

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        return qs.filter(product__store=ctx.store)

    def get_serializer_context(self):
        ctx = get_active_store(self.request)
        return {
            **super().get_serializer_context(),
            "store_id": ctx.store.pk if ctx.store else None,
        }

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError(
                {
                    'detail': (
                        'No active store resolved. Re-login, switch store, or send the '
                        'X-Store-ID header.'
                    )
                }
            )
        product = serializer.validated_data['product']
        if product.store_id != store.id:
            raise ValidationError(
                {'product': 'This product does not belong to your active store.'}
            )
        serializer.save()
        invalidate_product_cache(store.public_id)

    def perform_destroy(self, instance):
        store_public_id = instance.product.store.public_id
        schedule_media_deletion(instance)
        super().perform_destroy(instance)
        invalidate_product_cache(store_public_id)


class AdminCategoryViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    """All categories for the store. List: roots by default, or `parent_public_id`, or `tree=1` for nested JSON."""
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = AdminCategorySerializer
    queryset = Category.objects.select_related("parent").order_by(
        "parent_id", "order", "name"
    )
    lookup_field = "public_id"

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(store=ctx.store)
        if self.action != "list":
            return qs
        raw_tree = (self.request.query_params.get("tree") or "").lower()
        if raw_tree in ("1", "true", "yes"):
            return qs
        qs = qs.annotate(
            _pc=Count("products", distinct=False),
            _child_count=Count("children", distinct=False),
        )
        parent_pid = (self.request.query_params.get("parent_public_id") or "").strip()
        if parent_pid:
            qs = qs.filter(parent__public_id=parent_pid)
        else:
            qs = qs.filter(parent__isnull=True)
        return qs

    def list(self, request, *args, **kwargs):
        raw_tree = (request.query_params.get("tree") or "").lower()
        if raw_tree in ("1", "true", "yes"):
            ctx = get_active_store(request)
            if not ctx.store:
                return Response([])
            return Response(build_admin_category_tree(ctx.store, request))
        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        ctx = get_active_store(self.request)
        return {
            **super().get_serializer_context(),
            "store_id": ctx.store.pk if ctx.store else None,
        }

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError(
                {
                    "detail": (
                        "No active store resolved. Re-login, switch store, or send the "
                        "X-Store-ID header."
                    )
                }
            )
        instance = serializer.save(store=store)
        invalidate_category_cache(store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="category",
            entity_id=instance.public_id,
            summary=f"Category created: {getattr(instance, 'name', '')}".strip() or "Category created",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        ctx = get_active_store(self.request)
        if ctx.store:
            invalidate_category_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="category",
            entity_id=instance.public_id,
            summary=f"Category updated: {getattr(instance, 'name', '')}".strip() or "Category updated",
        )

    def perform_destroy(self, instance):
        name = getattr(instance, "name", "")
        public_id = instance.public_id
        schedule_media_deletion(instance)
        ctx = get_active_store(self.request)
        super().perform_destroy(instance)
        if ctx.store:
            invalidate_category_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="category",
            entity_id=public_id,
            summary=f"Category deleted: {name}" if name else "Category deleted",
        )


class AdminProductVariantViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = AdminProductVariantSerializer
    queryset = (
        ProductVariant.objects.select_related("product", "product__store", "store", "inventory")
        .prefetch_related("attribute_values__attribute_value__attribute")
        .all()
    )
    lookup_field = "public_id"

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(product__store=ctx.store)
        product_public_id = self.request.query_params.get("product_public_id")
        if product_public_id:
            qs = qs.filter(product__public_id=product_public_id)
        if self.action == "list" and not include_inactive_truthy(self.request):
            qs = qs.filter(is_active=True)
        return qs.order_by("product__public_id", "sku", "id")

    def get_serializer_context(self):
        ctx = get_active_store(self.request)
        return {
            **super().get_serializer_context(),
            "store_id": ctx.store.pk if ctx.store else None,
        }

    def _ensure_product_in_store(self, product: Product) -> None:
        ctx = get_active_store(self.request)
        store = ctx.store
        if not store:
            raise ValidationError(
                {
                    "detail": (
                        "No active store resolved. Re-login, switch store, or send the "
                        "X-Store-ID header."
                    )
                }
            )
        if product.store_id != store.id:
            raise ValidationError(
                {"product": "This product does not belong to your active store."}
            )

    def perform_create(self, serializer):
        product = serializer.validated_data["product"]
        self._ensure_product_in_store(product)
        instance = serializer.save()
        ctx = get_active_store(self.request)
        if ctx.store:
            invalidate_product_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="product_variant",
            entity_id=instance.public_id,
            summary=f"Variant created: {instance.sku} ({instance.product.name})",
        )

    def perform_update(self, serializer):
        product = serializer.validated_data.get("product", serializer.instance.product)
        self._ensure_product_in_store(product)
        instance = serializer.save()
        ctx = get_active_store(self.request)
        if ctx.store:
            invalidate_product_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="product_variant",
            entity_id=instance.public_id,
            summary=f"Variant updated: {instance.sku}",
        )

    def perform_destroy(self, instance):
        self._ensure_product_in_store(instance.product)
        product = instance.product
        sku = instance.sku
        variant_public_id = instance.public_id
        ctx = get_active_store(self.request)
        super().perform_destroy(instance)
        if not product.variants.exists():
            from engine.apps.inventory.cache_sync import refresh_product_stock_cache

            with transaction.atomic():
                Inventory.objects.get_or_create(
                    product=product,
                    variant=None,
                    defaults={"quantity": clamp_stock(0)},
                )
                refresh_product_stock_cache(
                    store_id=int(product.store_id),
                    product_id=product.id,
                )
        if ctx.store:
            invalidate_product_cache(ctx.store.public_id)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="product_variant",
            entity_id=variant_public_id,
            summary=f"Variant deleted: {sku}",
        )


class AdminProductAttributeViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    """Store-scoped attribute definitions (Color, Size, …)."""
    serializer_class = AdminProductAttributeSerializer
    queryset = ProductAttribute.objects.prefetch_related("values").order_by("order", "name")
    lookup_field = "public_id"

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        return qs.filter(store=ctx.store)

    def get_serializer_context(self):
        ctx = get_active_store(self.request)
        return {
            **super().get_serializer_context(),
            "store_id": ctx.store.pk if ctx.store else None,
        }

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        if not ctx.store:
            raise ValidationError({"detail": "No active store resolved."})
        instance = serializer.save(store=ctx.store)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="product_attribute",
            entity_id=instance.public_id,
            summary=f"Product attribute created: {instance.name}",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="product_attribute",
            entity_id=instance.public_id,
            summary=f"Product attribute updated: {instance.name}",
        )

    def perform_destroy(self, instance):
        public_id = instance.public_id
        name = instance.name
        super().perform_destroy(instance)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="product_attribute",
            entity_id=public_id,
            summary=f"Product attribute deleted: {name}",
        )


class AdminProductAttributeValueViewSet(StoreRolePermissionMixin, viewsets.ModelViewSet):
    serializer_class = AdminProductAttributeValueSerializer
    queryset = ProductAttributeValue.objects.select_related("attribute").order_by(
        "attribute", "order", "value"
    )
    lookup_field = "public_id"

    def get_queryset(self):
        qs = super().get_queryset()
        ctx = get_active_store(self.request)
        if not ctx.store:
            return qs.none()
        qs = qs.filter(store=ctx.store)
        # Do NOT accept ?attribute=<int> (internal PK) — use attribute_public_id instead
        attr_public_id = self.request.query_params.get("attribute_public_id")
        if attr_public_id:
            qs = qs.filter(attribute__public_id=attr_public_id)
        return qs

    def get_serializer_context(self):
        ctx = get_active_store(self.request)
        return {
            **super().get_serializer_context(),
            "store_id": ctx.store.pk if ctx.store else None,
        }

    def perform_create(self, serializer):
        ctx = get_active_store(self.request)
        if not ctx.store:
            raise ValidationError({"detail": "No active store resolved."})
        instance = serializer.save(store=ctx.store)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.CREATE,
            entity_type="product_attribute_value",
            entity_id=instance.public_id,
            summary=f"Attribute value created: {instance}",
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity(
            request=self.request,
            action=ActivityLog.Action.UPDATE,
            entity_type="product_attribute_value",
            entity_id=instance.public_id,
            summary=f"Attribute value updated: {instance}",
        )

    def perform_destroy(self, instance):
        public_id = instance.public_id
        label = str(instance)
        super().perform_destroy(instance)
        log_activity(
            request=self.request,
            action=ActivityLog.Action.DELETE,
            entity_type="product_attribute_value",
            entity_id=public_id,
            summary=f"Attribute value deleted: {label}",
        )

