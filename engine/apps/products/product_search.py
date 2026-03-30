"""Prioritized product text search: name and catalog fields before SKU (exact/prefix only)."""

from __future__ import annotations

from django.db.models import Case, IntegerField, QuerySet, When

from engine.apps.products.models import Product

# Cap per tier to keep search predictable on large catalogs.
_MAX_IDS_PER_TIER = 2000


def filter_products_by_prioritized_search(base_qs: QuerySet[Product], term: str) -> QuerySet[Product]:
    """
    Return products matching ``term`` ordered by relevance:
    name, brand, category name, description, variant attribute values,
    then variant SKU (exact match), then variant SKU (prefix match only).
    Substring SKU match (icontains) is intentionally excluded so SKU does not dominate.
    """
    q = (term or "").strip()
    if not q:
        return base_qs

    ordered_pks: list[int] = []
    seen: set[int] = set()

    def extend(qs: QuerySet[Product]) -> None:
        pks = list(qs.values_list("pk", flat=True).distinct()[:_MAX_IDS_PER_TIER])
        for pk in pks:
            if pk not in seen:
                seen.add(pk)
                ordered_pks.append(pk)

    extend(base_qs.filter(name__icontains=q))
    extend(base_qs.filter(brand__icontains=q))
    extend(base_qs.filter(category__name__icontains=q))
    extend(base_qs.filter(description__icontains=q))
    extend(
        base_qs.filter(
            variants__attribute_values__attribute_value__value__icontains=q,
        )
    )
    extend(base_qs.filter(variants__sku__iexact=q))
    extend(base_qs.filter(variants__sku__istartswith=q))

    if not ordered_pks:
        return base_qs.none()

    preserved = Case(
        *[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_pks)],
        output_field=IntegerField(),
    )
    return base_qs.filter(pk__in=ordered_pks).order_by(preserved)
