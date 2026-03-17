from django.db import models

from engine.apps.stores.models import Store


class AttributeDefinition(models.Model):
    """Per-store attribute definition for different entity types (product, variant, category, customer, order)."""

    class EntityType(models.TextChoices):
        PRODUCT = "product", "Product"
        VARIANT = "variant", "Product variant"
        CATEGORY = "category", "Category"
        CUSTOMER = "customer", "Customer"
        ORDER = "order", "Order"

    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        BOOL = "bool", "Boolean"
        DATE = "date", "Date"
        SELECT = "select", "Select"
        MULTISELECT = "multiselect", "Multi select"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="attribute_definitions",
    )
    entity_type = models.CharField(
        max_length=20,
        choices=EntityType.choices,
    )
    key = models.SlugField(
        max_length=100,
        help_text="Internal key used in APIs (e.g. color, size).",
    )
    label = models.CharField(
        max_length=255,
        help_text="Human-readable label for dashboards/frontends.",
    )
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
    )
    required = models.BooleanField(default=False)
    filterable = models.BooleanField(
        default=False,
        help_text="Whether this attribute should be usable in filters/facets.",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    options = models.JSONField(
        blank=True,
        null=True,
        help_text="For select/multiselect types: list of allowed options.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "entity_type", "key"],
                name="uniq_attrdef_store_entity_key",
            ),
        ]
        ordering = ["store", "entity_type", "order", "key"]

    def __str__(self) -> str:
        return f"{self.store_id}:{self.entity_type}:{self.key}"


class BaseAttributeValue(models.Model):
    """Abstract base for typed attribute values."""

    definition = models.ForeignKey(
        AttributeDefinition,
        on_delete=models.CASCADE,
        related_name="%(class)s_values",
    )

    # Typed value columns - only one is expected to be used per row,
    # depending on definition.field_type.
    value_text = models.TextField(blank=True, null=True)
    value_number = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        blank=True,
        null=True,
    )
    value_bool = models.BooleanField(blank=True, null=True)
    value_date = models.DateField(blank=True, null=True)

    class Meta:
        abstract = True

    def clean(self):
        # Basic invariant: at least one value_* is set.
        if not any(
            [
                self.value_text not in (None, ""),
                self.value_number is not None,
                self.value_bool is not None,
                self.value_date is not None,
            ]
        ):
            from django.core.exceptions import ValidationError

            raise ValidationError("Attribute value cannot be entirely empty.")


class ProductAttributeValue(BaseAttributeValue):
    """Attribute value attached to a Product."""

    from engine.apps.products.models import Product

    entity = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "definition"],
                name="uniq_product_attr_entity_definition",
            ),
        ]


class VariantAttributeValue(BaseAttributeValue):
    """Attribute value attached to a ProductVariant."""

    entity = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.CASCADE,
        related_name="entity_attribute_values",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "definition"],
                name="uniq_variant_attr_entity_definition",
            ),
        ]


class CategoryAttributeValue(BaseAttributeValue):
    """Attribute value attached to a Category."""

    entity = models.ForeignKey(
        "products.Category",
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "definition"],
                name="uniq_category_attr_entity_definition",
            ),
        ]


class CustomerAttributeValue(BaseAttributeValue):
    """Attribute value attached to a Customer."""

    entity = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "definition"],
                name="uniq_customer_attr_entity_definition",
            ),
        ]


class OrderAttributeValue(BaseAttributeValue):
    """Attribute value attached to an Order."""

    entity = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "definition"],
                name="uniq_order_attr_entity_definition",
            ),
        ]

