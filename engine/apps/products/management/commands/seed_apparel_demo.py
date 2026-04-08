"""
Seed a realistic apparel catalog with categories, products, and variants.

Usage:
  python manage.py seed_apparel_demo
  python manage.py seed_apparel_demo --store-id 4
  python manage.py seed_apparel_demo --force   # remove prior seeded products and re-seed
"""

from __future__ import annotations

from pathlib import Path
from decimal import Decimal
import json
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from engine.apps.products.models import (
    Category,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttribute,
)
from engine.apps.inventory.models import Inventory
from engine.apps.inventory.utils import clamp_stock
from engine.apps.stores.models import Store, StoreSettings
from engine.core.tenant_execution import tenant_scope_from_store


SEED_TAG_KEY = "seed_source"
SEED_TAG_VALUE = "apparel_v1"

# Attribute slugs (unique) — prefixed to avoid clashing with existing catalog data
ATTR_COLOR = "seed-color"
ATTR_SIZE = "seed-size"
ATTR_WAIST = "seed-waist"
ATTR_FIT = "seed-fit"
ATTR_SHOE_SIZE = "seed-shoe-size"
ATTR_HAT_SIZE = "seed-hat-size"

COLORS = [
    ("Black", "BLK"),
    ("White", "WHT"),
    ("Navy", "NVY"),
    ("Olive", "OLV"),
    ("Burgundy", "BRG"),
    ("Tan", "TAN"),
]
SIZES = ["XS", "S", "M", "L", "XL"]
WAISTS = ["30", "32", "34", "36", "38"]
FITS = [("Regular", "REG"), ("Slim", "SLM")]
SHOE_SIZES = ["7", "8", "9", "10", "11", "12"]
HAT_SIZES = ["S/M", "L/XL"]


def _money(v: str | Decimal) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(v)


def _seed_file_path(filename: str) -> Path:
    backend_root = Path(__file__).resolve().parents[5]
    return backend_root / "seeds" / "products" / filename


def _load_seed_data_from_json() -> dict:
    file_path = _seed_file_path("seed_apparel_demo.json")
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


_seed_data = _load_seed_data_from_json()
SEED_TAG_KEY = _seed_data.get("SEED_TAG_KEY", SEED_TAG_KEY)
SEED_TAG_VALUE = _seed_data.get("SEED_TAG_VALUE", SEED_TAG_VALUE)
ATTR_COLOR = _seed_data.get("ATTR_COLOR", ATTR_COLOR)
ATTR_SIZE = _seed_data.get("ATTR_SIZE", ATTR_SIZE)
ATTR_WAIST = _seed_data.get("ATTR_WAIST", ATTR_WAIST)
ATTR_FIT = _seed_data.get("ATTR_FIT", ATTR_FIT)
ATTR_SHOE_SIZE = _seed_data.get("ATTR_SHOE_SIZE", ATTR_SHOE_SIZE)
ATTR_HAT_SIZE = _seed_data.get("ATTR_HAT_SIZE", ATTR_HAT_SIZE)
COLORS = [tuple(row) for row in _seed_data.get("COLORS", COLORS)]
SIZES = _seed_data.get("SIZES", SIZES)
WAISTS = _seed_data.get("WAISTS", WAISTS)
FITS = [tuple(row) for row in _seed_data.get("FITS", FITS)]
SHOE_SIZES = _seed_data.get("SHOE_SIZES", SHOE_SIZES)
HAT_SIZES = _seed_data.get("HAT_SIZES", HAT_SIZES)


class Command(BaseCommand):
    help = (
        "Seed a demo apparel catalog: 7+ categories, 3+ child categories each, "
        "5–6 products per child category with variants, inventory, and extra_data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            type=int,
            default=None,
            help="Store primary key (default: first active store)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing demo products (by name) for this store and re-seed",
        )

    def handle(self, *args, **options):
        store_id = options.get("store_id")
        force = options.get("force", False)

        if store_id is not None:
            store = Store.objects.filter(pk=store_id, is_active=True).first()
            if not store:
                self.stderr.write(self.style.ERROR(f"No active store with id={store_id}"))
                return
        else:
            store = Store.objects.filter(is_active=True).order_by("id").first()
            if not store:
                self.stderr.write(self.style.ERROR("No active store found."))
                return

        self.stdout.write(f"Using store: {store.name!r} (id={store.pk})")

        with tenant_scope_from_store(store=store, reason="seed_apparel_demo_command"):
            with transaction.atomic():
                if force:
                    self._delete_demo_products(store)

                category_map = self._ensure_categories(store)
                attr_map = self._ensure_attributes(store)
                self._merge_demo_extra_schema(store)
                seeded = self._seed_catalog(store=store, category_map=category_map, attr_map=attr_map)

            self._sync_stock_cache(store)
            self.stdout.write(self.style.SUCCESS(f"Done. Seeded/updated {seeded} products."))

    def _delete_demo_products(self, store: Store) -> None:
        # Use the direct JSON key lookup; works on Postgres and on SQLite when JSON1 is enabled.
        qs = Product.objects.filter(store=store, **{f"extra_data__{SEED_TAG_KEY}": SEED_TAG_VALUE})
        n, _ = qs.delete()
        if n:
            self.stdout.write(self.style.WARNING(f"Removed {n} demo product rows (and dependents)."))

    def _ensure_categories(self, store: Store) -> dict[str, Category]:
        """
        Create a demo category tree with 7 ROOT categories and 3 child categories each.

        Note: Category.slug is auto-generated from name, so we match by (store, name, parent).
        """
        tree: list[tuple[str, str, list[tuple[str, str]]]] = [
            ("men", "Men", [("men-tees", "Tees"), ("men-shirts", "Shirts"), ("men-pants", "Pants")]),
            ("women", "Women", [("women-tops", "Tops"), ("women-dresses", "Dresses"), ("women-bottoms", "Bottoms")]),
            ("kids", "Kids", [("kids-boys", "Boys"), ("kids-girls", "Girls"), ("kids-baby", "Baby")]),
            ("footwear", "Footwear", [("footwear-sneakers", "Sneakers"), ("footwear-boots", "Boots"), ("footwear-sandals", "Sandals")]),
            ("accessories", "Accessories", [("acc-hats", "Hats"), ("acc-bags", "Bags"), ("acc-belts", "Belts")]),
            ("outerwear", "Outerwear", [("outerwear-jackets", "Jackets"), ("outerwear-hoodies", "Hoodies"), ("outerwear-coats", "Coats")]),
            ("activewear", "Activewear", [("active-tops", "Training Tops"), ("active-bottoms", "Training Bottoms"), ("active-sets", "Sets")]),
        ]

        # Optional deeper nesting (3rd level) for a few categories, e.g. Men → Shirts → Button-Downs.
        nested: dict[str, list[tuple[str, str]]] = {
            "men-shirts": [
                ("men-shirts-button-downs", "Button-Downs"),
                ("men-shirts-overshirts", "Overshirts"),
                ("men-shirts-casual", "Casual Shirts"),
            ],
            "footwear-sneakers": [
                ("footwear-sneakers-running", "Running"),
                ("footwear-sneakers-court", "Court"),
                ("footwear-sneakers-trail", "Trail"),
            ],
        }

        # Deep (max depth) branches: MAX_CATEGORY_DEPTH is 5 (root = 1).
        # We create a few 5-level paths so the storefront has "fully nested" examples.
        deep_paths: list[list[tuple[str, str, str]]] = [
            # Men (root) → Shirts → Button-Downs → Oxford → Long Sleeve
            [
                ("men", "Men", "men"),
                ("men-shirts", "Shirts", "men"),
                ("men-shirts-button-downs", "Button-Downs", "men-shirts"),
                ("men-shirts-button-downs-oxford", "Oxford", "men-shirts-button-downs"),
                ("men-shirts-button-downs-oxford-long-sleeve", "Long Sleeve", "men-shirts-button-downs-oxford"),
            ],
            # Footwear (root) → Sneakers → Running → Cushioned → Daily Trainer
            [
                ("footwear", "Footwear", "footwear"),
                ("footwear-sneakers", "Sneakers", "footwear"),
                ("footwear-sneakers-running", "Running", "footwear-sneakers"),
                ("footwear-sneakers-running-cushioned", "Cushioned", "footwear-sneakers-running"),
                ("footwear-sneakers-running-cushioned-daily", "Daily Trainer", "footwear-sneakers-running-cushioned"),
            ],
        ]

        # Migration path: earlier versions created a single root "Apparel" category and nested the
        # 7 main categories under it. If that exists, lift those categories to the true root so
        # the storefront shows 7 root categories as expected.
        legacy_root = Category.objects.filter(store=store, name="Apparel", parent=None).first()

        category_map: dict[str, Category] = {}
        order = 0
        for parent_key, parent_name, children in tree:
            parent_cat = Category.objects.filter(store=store, name=parent_name, parent=None).first()
            if not parent_cat and legacy_root:
                # If the parent exists under legacy_root, lift it to root.
                legacy_parent = Category.objects.filter(
                    store=store,
                    name=parent_name,
                    parent=legacy_root,
                ).first()
                if legacy_parent:
                    legacy_parent.parent = None
                    legacy_parent.order = order
                    legacy_parent.is_active = True
                    legacy_parent.description = legacy_parent.description or f"{parent_name} collection"
                    legacy_parent.save()
                    parent_cat = legacy_parent

            if not parent_cat:
                parent_cat = Category.objects.create(
                    store=store,
                    name=parent_name,
                    parent=None,
                    description=f"{parent_name} collection",
                    order=order,
                    is_active=True,
                )
            else:
                # Keep parent categories consistent across runs.
                updates: list[str] = []
                if parent_cat.order != order:
                    parent_cat.order = order
                    updates.append("order")
                if not parent_cat.is_active:
                    parent_cat.is_active = True
                    updates.append("is_active")
                if not (parent_cat.description or "").strip():
                    parent_cat.description = f"{parent_name} collection"
                    updates.append("description")
                if updates:
                    parent_cat.save(update_fields=updates)
            category_map[parent_key] = parent_cat
            order += 1

            child_order = 1
            for child_key, child_name in children:
                # If the child exists under the legacy tree, ensure it is under the lifted/new parent.
                child_cat = Category.objects.filter(store=store, name=child_name, parent=parent_cat).first()
                if not child_cat and legacy_root:
                    legacy_parent = Category.objects.filter(store=store, name=parent_name, parent=legacy_root).first()
                    if legacy_parent:
                        legacy_child = Category.objects.filter(store=store, name=child_name, parent=legacy_parent).first()
                        if legacy_child:
                            legacy_child.parent = parent_cat
                            legacy_child.order = child_order
                            legacy_child.is_active = True
                            if not (legacy_child.description or "").strip():
                                legacy_child.description = f"{child_name} in {parent_name}"
                            legacy_child.save()
                            child_cat = legacy_child

                if not child_cat:
                    child_cat = Category.objects.create(
                        store=store,
                        name=child_name,
                        parent=parent_cat,
                        description=f"{child_name} in {parent_name}",
                        order=child_order,
                        is_active=True,
                    )
                else:
                    updates: list[str] = []
                    if child_cat.order != child_order:
                        child_cat.order = child_order
                        updates.append("order")
                    if not child_cat.is_active:
                        child_cat.is_active = True
                        updates.append("is_active")
                    if not (child_cat.description or "").strip():
                        child_cat.description = f"{child_name} in {parent_name}"
                        updates.append("description")
                    if updates:
                        child_cat.save(update_fields=updates)
                category_map[child_key] = child_cat
                child_order += 1

                # Create 3rd-level nested categories where desired.
                if child_key in nested:
                    grand_order = 1
                    for grand_key, grand_name in nested[child_key]:
                        grand_cat = Category.objects.filter(
                            store=store,
                            name=grand_name,
                            parent=child_cat,
                        ).first()
                        if not grand_cat:
                            grand_cat = Category.objects.create(
                                store=store,
                                name=grand_name,
                                parent=child_cat,
                                description=f"{grand_name} in {child_name}",
                                order=grand_order,
                                is_active=True,
                            )
                        else:
                            updates2: list[str] = []
                            if grand_cat.order != grand_order:
                                grand_cat.order = grand_order
                                updates2.append("order")
                            if not grand_cat.is_active:
                                grand_cat.is_active = True
                                updates2.append("is_active")
                            if not (grand_cat.description or "").strip():
                                grand_cat.description = f"{grand_name} in {child_name}"
                                updates2.append("description")
                            if updates2:
                                grand_cat.save(update_fields=updates2)
                        category_map[grand_key] = grand_cat
                        grand_order += 1

        # Ensure deep paths exist up to max depth (5).
        for path in deep_paths:
            for key, name, parent_key in path:
                if key in category_map:
                    continue
                parent = category_map.get(parent_key)
                if parent is None:
                    # Parent is always created earlier in the loop (root categories and their children),
                    # but guard anyway for future edits.
                    continue
                existing = Category.objects.filter(store=store, name=name, parent=parent).first()
                if existing:
                    category_map[key] = existing
                    continue
                category_map[key] = Category.objects.create(
                    store=store,
                    name=name,
                    parent=parent,
                    description=f"{name} in {parent.name}",
                    order=1,
                    is_active=True,
                )

        if legacy_root and not legacy_root.children.exists():
            legacy_root.delete()

        return category_map

    def _ensure_attributes(self, store: Store) -> dict[str, ProductAttribute]:
        color_attr, _ = ProductAttribute.objects.get_or_create(
            store=store,
            slug=ATTR_COLOR,
            defaults={"name": "Color", "order": 1},
        )
        size_attr, _ = ProductAttribute.objects.get_or_create(
            store=store,
            slug=ATTR_SIZE,
            defaults={"name": "Size", "order": 2},
        )
        waist_attr, _ = ProductAttribute.objects.get_or_create(
            store=store,
            slug=ATTR_WAIST,
            defaults={"name": "Waist", "order": 3},
        )
        fit_attr, _ = ProductAttribute.objects.get_or_create(
            store=store,
            slug=ATTR_FIT,
            defaults={"name": "Fit", "order": 4},
        )
        shoe_size_attr, _ = ProductAttribute.objects.get_or_create(
            store=store,
            slug=ATTR_SHOE_SIZE,
            defaults={"name": "Shoe size", "order": 5},
        )
        hat_size_attr, _ = ProductAttribute.objects.get_or_create(
            store=store,
            slug=ATTR_HAT_SIZE,
            defaults={"name": "Hat size", "order": 6},
        )

        for order, (label, _code) in enumerate(COLORS):
            ProductAttributeValue.objects.get_or_create(
                store=store,
                attribute=color_attr,
                value=label,
                defaults={"order": order},
            )
        for order, sz in enumerate(SIZES):
            ProductAttributeValue.objects.get_or_create(
                store=store,
                attribute=size_attr,
                value=sz,
                defaults={"order": order},
            )
        for order, w in enumerate(WAISTS):
            ProductAttributeValue.objects.get_or_create(
                store=store,
                attribute=waist_attr,
                value=w,
                defaults={"order": order},
            )
        for order, (label, _code) in enumerate(FITS):
            ProductAttributeValue.objects.get_or_create(
                store=store,
                attribute=fit_attr,
                value=label,
                defaults={"order": order},
            )
        for order, s in enumerate(SHOE_SIZES):
            ProductAttributeValue.objects.get_or_create(
                store=store,
                attribute=shoe_size_attr,
                value=s,
                defaults={"order": order},
            )
        for order, s in enumerate(HAT_SIZES):
            ProductAttributeValue.objects.get_or_create(
                store=store,
                attribute=hat_size_attr,
                value=s,
                defaults={"order": order},
            )

        return {
            "color": color_attr,
            "size": size_attr,
            "waist": waist_attr,
            "fit": fit_attr,
            "shoe_size": shoe_size_attr,
            "hat_size": hat_size_attr,
        }

    def _merge_demo_extra_schema(self, store: Store) -> None:
        """Optional: add sample schema keys so dashboard extra fields match extra_data."""
        settings, _ = StoreSettings.objects.get_or_create(store=store)
        schema = list(settings.extra_field_schema or [])
        if not isinstance(schema, list):
            schema = []

        def has(name: str, entity: str = "product") -> bool:
            for row in schema:
                if not isinstance(row, dict):
                    continue
                if (row.get("name") or "").strip() == name and (
                    row.get("entityType") or row.get("entity_type")
                ) == entity:
                    return True
            return False

        next_order = max((int(r.get("order") or 0) for r in schema if isinstance(r, dict)), default=-1)

        def add_field(
            name: str,
            field_type: str,
            required: bool = False,
            options: list[str] | None = None,
        ) -> None:
            nonlocal next_order
            if has(name):
                return
            next_order += 1
            schema.append(
                {
                    "id": f"seed-{name.lower().replace(' ', '-')}",
                    "entityType": "product",
                    "name": name,
                    "fieldType": field_type,
                    "required": required,
                    "order": next_order,
                    **({"options": options} if options else {}),
                }
            )

        add_field("Material", "text")
        add_field("Care", "text")
        add_field("GSM", "text")  # shirt weight / fabric weight
        add_field("Inseam", "text")
        add_field("Rise", "dropdown", options=["Low-rise", "Mid-rise", "High-rise"])
        add_field("Fabric", "text")
        add_field("Fit notes", "text")
        add_field("Sole", "text")
        add_field("Closure", "dropdown", options=["Laces", "Slip-on", "Buckle", "Zipper"])
        add_field("Water resistance", "dropdown", options=["None", "Light", "Moderate", "High"])

        settings.extra_field_schema = schema
        settings.save(update_fields=["extra_field_schema"])

    def _value_map(self, attr: ProductAttribute) -> dict[str, ProductAttributeValue]:
        return {v.value: v for v in attr.values.all()}

    def _seed_catalog(
        self,
        *,
        store: Store,
        category_map: dict[str, Category],
        attr_map: dict[str, ProductAttribute],
    ) -> int:
        rng = random.Random(1337)

        values = {
            "color": self._value_map(attr_map["color"]),
            "size": self._value_map(attr_map["size"]),
            "waist": self._value_map(attr_map["waist"]),
            "fit": self._value_map(attr_map["fit"]),
            "shoe_size": self._value_map(attr_map["shoe_size"]),
            "hat_size": self._value_map(attr_map["hat_size"]),
        }

        # 7 top-level categories × 3 child categories each, with 5–6 products per child
        # Keep variant counts small per product (typically 6–10) so seeding stays fast.
        catalog: list[tuple[str, list[tuple[str, list[dict]]]]] = [
            (
                "men",
                [
                    (
                        "men-tees",
                        [
                            self._prod("Classic Crew Neck Tee", "Demo Essentials", "24.99", "32.00", "Soft everyday tee.", {"Material": "100% ringspun cotton", "GSM": "180 GSM"}, ("color", ["Black", "White", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Heavyweight Pocket Tee", "Demo Essentials", "29.99", "38.00", "Structured pocket tee.", {"Material": "100% cotton", "GSM": "240 GSM"}, ("color", ["White", "Olive", "Black"]), ("size", ["S", "M", "L"])),
                            self._prod("Relaxed Graphic Tee", "Demo Studio", "27.99", "35.00", "Relaxed fit tee with subtle print.", {"Material": "Cotton jersey", "GSM": "200 GSM"}, ("color", ["Navy", "Burgundy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Long Sleeve Henley", "Demo Essentials", "34.99", "45.00", "Layer-friendly henley.", {"Material": "Cotton blend"}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Performance Mesh Tee", "Demo Active", "22.99", "30.00", "Breathable training tee.", {"Fabric": "Poly mesh"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                    (
                        "men-shirts-button-downs",
                        [
                            self._prod("Oxford Button-Down Shirt", "Demo Classics", "49.99", "65.00", "Crisp oxford for work or weekend.", {"Fabric": "Oxford cotton", "Fit notes": "Runs true to size"}, ("color", ["White", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Linen Camp Collar Shirt", "Demo Classics", "54.99", "72.00", "Breezy linen camp collar.", {"Fabric": "Linen"}, ("color", ["Tan", "White"]), ("size", ["S", "M", "L"])),
                            self._prod("Stretch Poplin Shirt", "Demo Classics", "44.99", "60.00", "Easy-care stretch poplin.", {"Fabric": "Poplin stretch"}, ("color", ["White", "Black"]), ("size", ["S", "M", "L"])),
                            self._prod("Denim Work Shirt", "Demo Workwear", "64.99", "85.00", "Lightweight denim with snaps.", {"Fabric": "Chambray denim"}, ("color", ["Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Relaxed Button-Up Shirt", "Demo Classics", "46.99", "62.00", "Relaxed-fit button-up.", {"Fabric": "Cotton poplin", "Fit notes": "Relaxed"}, ("color", ["White", "Tan"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                    (
                        "men-shirts-overshirts",
                        [
                            self._prod("Flannel Overshirt", "Demo Outdoors", "59.99", "79.00", "Brushed flannel overshirt.", {"Fabric": "Brushed flannel"}, ("color", ["Olive", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Quilted Liner Overshirt", "Demo Outdoors", "74.99", "98.00", "Light quilted overshirt.", {"Fabric": "Quilted nylon", "Water resistance": "Light"}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Corduroy Overshirt", "Demo Studio", "64.99", "85.00", "Soft corduroy overshirt.", {"Fabric": "Corduroy"}, ("color", ["Tan", "Olive"]), ("size", ["S", "M", "L"])),
                            self._prod("Canvas Utility Overshirt", "Demo Workwear", "69.99", "92.00", "Hard-wearing utility overshirt.", {"Fabric": "Cotton canvas"}, ("color", ["Olive", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Wool Blend Overshirt", "Demo Classics", "84.99", "110.00", "Warm wool-blend overshirt.", {"Material": "Wool blend"}, ("color", ["Navy", "Black"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                    (
                        "men-pants",
                        [
                            self._prod("Stretch Chino Pant", "Demo Essentials", "59.99", "78.00", "Clean stretch chino. Standard 32\" inseam.", {"Material": "97% cotton, 3% elastane", "Inseam": '32"', "Rise": "Mid-rise"}, ("waist", ["30", "32", "34", "36"]), ("fit", ["Regular", "Slim"])),
                            self._prod("Tapered Travel Pant", "Demo Active", "69.99", "90.00", "Wrinkle-resistant travel pant.", {"Fabric": "Nylon blend", "Inseam": '30"'}, ("waist", ["30", "32", "34", "36"]), ("fit", ["Slim"])),
                            self._prod("Relaxed Cargo Pant", "Demo Workwear", "74.99", "98.00", "Utility cargo with roomy fit.", {"Fabric": "Cotton ripstop"}, ("waist", ["32", "34", "36", "38"]), ("fit", ["Regular"])),
                            self._prod("Selvedge Denim Jean", "Demo Studio", "109.99", "140.00", "Raw selvedge denim.", {"Fabric": "Selvedge denim", "Fit notes": "Expect break-in"}, ("waist", ["30", "32", "34", "36"]), ("fit", ["Slim"])),
                            self._prod("Everyday Jogger", "Demo Active", "49.99", "65.00", "Soft fleece jogger.", {"Fabric": "Fleece", "Fit notes": "Tapered leg"}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L", "XL"])),
                        ],
                    ),
                ],
            ),
            (
                "women",
                [
                    (
                        "women-tops",
                        [
                            self._prod("Ribbed Tank Top", "Demo Studio", "19.99", "28.00", "Ribbed tank with stretch.", {"Fabric": "Rib knit"}, ("color", ["White", "Black", "Olive"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Cropped Hoodie", "Demo Active", "54.99", "72.00", "Cropped fleece hoodie.", {"Fabric": "Fleece"}, ("color", ["Black", "Burgundy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Wrap Blouse", "Demo Classics", "44.99", "60.00", "Lightweight wrap blouse.", {"Fabric": "Viscose blend"}, ("color", ["White", "Navy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Oversized Button-Up", "Demo Classics", "49.99", "68.00", "Oversized, easy button-up.", {"Fabric": "Cotton poplin", "Fit notes": "Oversized"}, ("color", ["White", "Tan"]), ("size", ["XS", "S", "M"])),
                            self._prod("Breathable Training Tee", "Demo Active", "24.99", "32.00", "Quick-dry training tee.", {"Fabric": "Poly knit"}, ("color", ["Black", "Navy"]), ("size", ["XS", "S", "M", "L"])),
                        ],
                    ),
                    (
                        "women-dresses",
                        [
                            self._prod("Everyday Midi Dress", "Demo Studio", "69.99", "90.00", "Soft midi with a clean drape.", {"Fabric": "Jersey"}, ("color", ["Black", "Navy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Linen Slip Dress", "Demo Studio", "79.99", "105.00", "Minimal slip dress in linen.", {"Fabric": "Linen"}, ("color", ["Tan", "Black"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Wrap Day Dress", "Demo Classics", "74.99", "98.00", "Flattering wrap silhouette.", {"Fabric": "Viscose"}, ("color", ["Burgundy", "Navy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Sweater Dress", "Demo Classics", "84.99", "110.00", "Knit sweater dress.", {"Fabric": "Knit blend"}, ("color", ["Black", "Olive"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Maxi Shirt Dress", "Demo Classics", "89.99", "120.00", "Button-front shirt dress.", {"Fabric": "Poplin"}, ("color", ["White", "Navy"]), ("size", ["XS", "S", "M"])),
                        ],
                    ),
                    (
                        "women-bottoms",
                        [
                            self._prod("High-Rise Legging", "Demo Active", "48.99", "64.00", "High-rise training legging.", {"Fabric": "Nylon stretch", "Rise": "High-rise"}, ("color", ["Black", "Navy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Relaxed Straight Jean", "Demo Studio", "89.99", "120.00", "Relaxed straight denim.", {"Fabric": "Denim", "Rise": "Mid-rise"}, ("waist", ["30", "32", "34", "36"]), ("fit", ["Regular"])),
                            self._prod("Pleated Trouser", "Demo Classics", "79.99", "105.00", "Pleated trouser with drape.", {"Fabric": "Poly-viscose"}, ("waist", ["30", "32", "34", "36"]), ("fit", ["Regular"])),
                            self._prod("A-Line Midi Skirt", "Demo Studio", "59.99", "78.00", "A-line skirt with movement.", {"Fabric": "Sateen"}, ("color", ["Black", "Tan"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Fleece Jogger", "Demo Active", "52.99", "70.00", "Cozy jogger.", {"Fabric": "Fleece"}, ("color", ["Black", "Olive"]), ("size", ["XS", "S", "M", "L"])),
                        ],
                    ),
                ],
            ),
            (
                "kids",
                [
                    (
                        "kids-boys",
                        [
                            self._prod("Kids Graphic Tee", "Demo Kids", "16.99", "22.00", "Soft tee with fun print.", {"Material": "Cotton jersey"}, ("color", ["Navy", "White"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Hoodie", "Demo Kids", "34.99", "45.00", "Warm fleece hoodie.", {"Fabric": "Fleece"}, ("color", ["Black", "Olive"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Jogger", "Demo Kids", "28.99", "38.00", "Everyday jogger.", {"Fabric": "Fleece"}, ("color", ["Navy", "Black"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Chino Short", "Demo Kids", "24.99", "32.00", "Stretch chino short.", {"Fabric": "Cotton stretch"}, ("waist", ["30", "32", "34"]), ("fit", ["Regular"])),
                            self._prod("Kids Polo Shirt", "Demo Kids", "22.99", "30.00", "Classic polo.", {"Fabric": "Pique cotton"}, ("color", ["White", "Navy"]), ("size", ["XS", "S", "M"])),
                        ],
                    ),
                    (
                        "kids-girls",
                        [
                            self._prod("Kids Ribbed Tee", "Demo Kids", "15.99", "20.00", "Ribbed tee with stretch.", {"Fabric": "Rib knit"}, ("color", ["White", "Burgundy"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Legging", "Demo Kids", "19.99", "26.00", "Soft legging.", {"Fabric": "Cotton stretch"}, ("color", ["Black", "Navy"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Dress", "Demo Kids", "29.99", "40.00", "Easy day dress.", {"Fabric": "Jersey"}, ("color", ["Navy", "Tan"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Cardigan", "Demo Kids", "32.99", "44.00", "Light cardigan.", {"Fabric": "Knit blend"}, ("color", ["Olive", "White"]), ("size", ["XS", "S", "M"])),
                            self._prod("Kids Skirt", "Demo Kids", "22.99", "30.00", "A-line skirt.", {"Fabric": "Sateen"}, ("color", ["Black", "Burgundy"]), ("size", ["XS", "S", "M"])),
                        ],
                    ),
                    (
                        "kids-baby",
                        [
                            self._prod("Baby Onesie", "Demo Baby", "14.99", "20.00", "Soft snap onesie.", {"Material": "Cotton"}, ("color", ["White", "Tan"]), ("size", ["XS", "S"])),
                            self._prod("Baby Sleep Set", "Demo Baby", "24.99", "34.00", "Two-piece sleep set.", {"Fabric": "Cotton rib"}, ("color", ["Navy", "Olive"]), ("size", ["XS", "S"])),
                            self._prod("Baby Knit Hat", "Demo Baby", "9.99", "14.00", "Warm knit hat.", {"Material": "Knit blend"}, ("hat_size", ["S/M", "L/XL"])),
                            self._prod("Baby Zip Hoodie", "Demo Baby", "26.99", "36.00", "Zip hoodie.", {"Fabric": "Fleece", "Closure": "Zipper"}, ("color", ["Tan", "Olive"]), ("size", ["XS", "S"])),
                            self._prod("Baby Jogger", "Demo Baby", "18.99", "26.00", "Soft jogger.", {"Fabric": "Fleece"}, ("color", ["Navy", "Black"]), ("size", ["XS", "S"])),
                        ],
                    ),
                ],
            ),
            (
                "footwear",
                [
                    (
                        "footwear-sneakers-running",
                        [
                            self._prod("Everyday Runner Sneaker", "Demo Footwear", "89.99", "120.00", "Cushioned runner.", {"Sole": "EVA", "Closure": "Laces"}, ("color", ["White", "Black"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Lightweight Tempo Runner", "Demo Footwear", "94.99", "125.00", "Light trainer for tempo runs.", {"Sole": "EVA", "Closure": "Laces"}, ("color", ["Black", "Navy"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Stability Runner", "Demo Footwear", "99.99", "135.00", "Stability support runner.", {"Sole": "EVA", "Closure": "Laces"}, ("color", ["White", "Navy"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Daily Trainer", "Demo Footwear", "84.99", "110.00", "Everyday training shoe.", {"Sole": "EVA", "Closure": "Laces"}, ("color", ["White", "Tan"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Recovery Runner", "Demo Footwear", "79.99", "100.00", "Soft recovery ride.", {"Sole": "EVA", "Closure": "Laces"}, ("color", ["Black", "White"]), ("shoe_size", ["8", "9", "10"])),
                        ],
                    ),
                    (
                        "footwear-sneakers-court",
                        [
                            self._prod("Court Low Sneaker", "Demo Footwear", "84.99", "110.00", "Clean court silhouette.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["White", "Navy"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Court Mid Sneaker", "Demo Footwear", "92.99", "125.00", "Mid-top court style.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["White", "Black"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Leather Court Sneaker", "Demo Footwear", "99.99", "135.00", "Leather upper court shoe.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["White", "Tan"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Minimal Court Sneaker", "Demo Footwear", "79.99", "105.00", "Minimal court sneaker.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["White", "Navy"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Retro Court Sneaker", "Demo Footwear", "89.99", "120.00", "Retro court details.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["White", "Black"]), ("shoe_size", ["8", "9", "10"])),
                        ],
                    ),
                    (
                        "footwear-sneakers-trail",
                        [
                            self._prod("Slip-On Knit Sneaker", "Demo Footwear", "79.99", "100.00", "Easy slip-on knit.", {"Sole": "Rubber", "Closure": "Slip-on"}, ("color", ["Black", "Olive"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Trail Sneaker", "Demo Outdoors", "99.99", "130.00", "Grippy trail runner.", {"Sole": "Rubber lug", "Water resistance": "Moderate"}, ("color", ["Black", "Navy"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Retro Runner", "Demo Footwear", "94.99", "125.00", "Retro-inspired runner.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["White", "Tan"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Water-Resistant Trail Shoe", "Demo Outdoors", "109.99", "145.00", "Trail shoe with water resistance.", {"Sole": "Rubber lug", "Water resistance": "High"}, ("color", ["Black", "Olive"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Light Trail Runner", "Demo Outdoors", "89.99", "120.00", "Light trail runner.", {"Sole": "Rubber lug", "Water resistance": "Light"}, ("color", ["Navy", "Olive"]), ("shoe_size", ["9", "10", "11"])),
                        ],
                    ),
                    (
                        "footwear-boots",
                        [
                            self._prod("Leather Chelsea Boot", "Demo Footwear", "149.99", "200.00", "Classic chelsea boot.", {"Sole": "Rubber", "Closure": "Slip-on", "Water resistance": "Light"}, ("color", ["Black", "Tan"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Hiker Boot", "Demo Outdoors", "159.99", "215.00", "Rugged hiker boot.", {"Sole": "Rubber lug", "Closure": "Laces", "Water resistance": "High"}, ("color", ["Black", "Olive"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Desert Boot", "Demo Footwear", "129.99", "175.00", "Suede desert boot.", {"Sole": "Crepe", "Closure": "Laces", "Water resistance": "None"}, ("color", ["Tan", "Olive"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("City Lace-Up Boot", "Demo Footwear", "139.99", "190.00", "Sleek lace-up boot.", {"Sole": "Rubber", "Closure": "Laces"}, ("color", ["Black", "Navy"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Winter Boot", "Demo Outdoors", "169.99", "230.00", "Insulated winter boot.", {"Sole": "Rubber lug", "Water resistance": "High", "Closure": "Zipper"}, ("color", ["Black"]), ("shoe_size", ["9", "10", "11"])),
                        ],
                    ),
                    (
                        "footwear-sandals",
                        [
                            self._prod("Two-Strap Sandal", "Demo Footwear", "49.99", "68.00", "Everyday two-strap sandal.", {"Sole": "EVA", "Closure": "Buckle"}, ("color", ["Black", "Tan"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Slide Sandal", "Demo Footwear", "34.99", "48.00", "Pool-ready slide.", {"Sole": "EVA", "Closure": "Slip-on"}, ("color", ["Black", "White"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Sport Sandal", "Demo Outdoors", "59.99", "82.00", "Trail-friendly sandal.", {"Sole": "Rubber", "Closure": "Buckle", "Water resistance": "Moderate"}, ("color", ["Black", "Olive"]), ("shoe_size", ["9", "10", "11"])),
                            self._prod("Leather Slide", "Demo Footwear", "54.99", "74.00", "Leather strap slide.", {"Sole": "Rubber", "Closure": "Slip-on"}, ("color", ["Tan", "Black"]), ("shoe_size", ["8", "9", "10"])),
                            self._prod("Minimal Thong Sandal", "Demo Footwear", "29.99", "42.00", "Minimal thong sandal.", {"Sole": "EVA"}, ("color", ["Black", "Tan"]), ("shoe_size", ["8", "9", "10"])),
                        ],
                    ),
                ],
            ),
            (
                "accessories",
                [
                    (
                        "acc-hats",
                        [
                            self._prod("Classic Baseball Cap", "Demo Essentials", "24.99", "34.00", "Everyday cap.", {"Material": "Cotton twill"}, ("color", ["Black", "Navy", "Olive"]), ("hat_size", ["S/M", "L/XL"])),
                            self._prod("Knit Beanie", "Demo Essentials", "19.99", "28.00", "Warm rib-knit beanie.", {"Material": "Knit blend"}, ("color", ["Black", "Tan"]), ("hat_size", ["S/M", "L/XL"])),
                            self._prod("Bucket Hat", "Demo Studio", "22.99", "32.00", "Casual bucket hat.", {"Material": "Cotton"}, ("color", ["White", "Olive"]), ("hat_size", ["S/M", "L/XL"])),
                            self._prod("Dad Hat", "Demo Essentials", "21.99", "30.00", "Relaxed dad hat.", {"Material": "Cotton"}, ("color", ["Navy", "Burgundy"]), ("hat_size", ["S/M", "L/XL"])),
                            self._prod("Five-Panel Cap", "Demo Active", "23.99", "34.00", "Lightweight cap.", {"Material": "Nylon"}, ("color", ["Black", "Olive"]), ("hat_size", ["S/M", "L/XL"])),
                        ],
                    ),
                    (
                        "acc-bags",
                        [
                            self._prod("Everyday Tote Bag", "Demo Essentials", "29.99", "40.00", "Sturdy canvas tote.", {"Material": "Canvas"}, ("color", ["Tan", "Black"])),
                            self._prod("Crossbody Bag", "Demo Studio", "44.99", "60.00", "Compact crossbody.", {"Material": "Nylon", "Closure": "Zipper"}, ("color", ["Black", "Olive"])),
                            self._prod("Mini Backpack", "Demo Studio", "54.99", "75.00", "Small backpack.", {"Material": "Nylon", "Closure": "Zipper"}, ("color", ["Black", "Navy"])),
                            self._prod("Weekender Duffel", "Demo Essentials", "79.99", "110.00", "Roomy weekender.", {"Material": "Canvas", "Closure": "Zipper"}, ("color", ["Tan", "Navy"])),
                            self._prod("Sling Bag", "Demo Active", "39.99", "55.00", "Hands-free sling.", {"Material": "Nylon", "Closure": "Zipper"}, ("color", ["Black", "Olive"])),
                        ],
                    ),
                    (
                        "acc-belts",
                        [
                            self._prod("Leather Belt", "Demo Classics", "39.99", "55.00", "Full-grain leather belt.", {"Material": "Leather"}, ("color", ["Black", "Tan"])),
                            self._prod("Woven Belt", "Demo Classics", "29.99", "42.00", "Stretch woven belt.", {"Material": "Woven elastic"}, ("color", ["Navy", "Tan"])),
                            self._prod("Canvas Web Belt", "Demo Workwear", "19.99", "28.00", "Durable web belt.", {"Material": "Canvas"}, ("color", ["Black", "Olive"])),
                            self._prod("Reversible Belt", "Demo Classics", "44.99", "62.00", "Two-in-one belt.", {"Material": "Leather"}, ("color", ["Black", "Tan"])),
                            self._prod("Utility Belt", "Demo Workwear", "24.99", "35.00", "Workwear utility belt.", {"Material": "Nylon"}, ("color", ["Black", "Olive"])),
                        ],
                    ),
                ],
            ),
            (
                "outerwear",
                [
                    (
                        "outerwear-jackets",
                        [
                            self._prod("Lightweight Bomber Jacket", "Demo Studio", "99.99", "130.00", "Light bomber with clean lines.", {"Fabric": "Nylon", "Water resistance": "Light"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Denim Jacket", "Demo Studio", "89.99", "120.00", "Classic denim jacket.", {"Fabric": "Denim"}, ("color", ["Navy", "Black"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Coach Jacket", "Demo Active", "74.99", "98.00", "Snap-front coach jacket.", {"Fabric": "Nylon", "Closure": "Slip-on", "Water resistance": "Moderate"}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L"])),
                            self._prod("Field Jacket", "Demo Outdoors", "119.99", "160.00", "Utility field jacket.", {"Fabric": "Cotton canvas", "Water resistance": "Light"}, ("color", ["Olive", "Tan"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Puffer Jacket", "Demo Outdoors", "139.99", "190.00", "Insulated puffer.", {"Fabric": "Ripstop", "Water resistance": "Moderate"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                    (
                        "outerwear-hoodies",
                        [
                            self._prod("Essential Pullover Hoodie", "Demo Essentials", "59.99", "78.00", "Soft pullover hoodie.", {"Fabric": "Fleece"}, ("color", ["Black", "Olive", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Zip Hoodie", "Demo Essentials", "64.99", "85.00", "Zip hoodie for layering.", {"Fabric": "Fleece", "Closure": "Zipper"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Heavyweight Hoodie", "Demo Studio", "74.99", "98.00", "Heavy fleece hoodie.", {"Fabric": "Heavy fleece"}, ("color", ["Black", "Burgundy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("French Terry Hoodie", "Demo Active", "62.99", "82.00", "Breathable terry hoodie.", {"Fabric": "French terry"}, ("color", ["Navy", "Olive"]), ("size", ["S", "M", "L"])),
                            self._prod("Cropped Hoodie", "Demo Active", "54.99", "72.00", "Cropped fit hoodie.", {"Fabric": "Fleece"}, ("color", ["Black", "Burgundy"]), ("size", ["XS", "S", "M", "L"])),
                        ],
                    ),
                    (
                        "outerwear-coats",
                        [
                            self._prod("Wool Blend Overcoat", "Demo Classics", "189.99", "250.00", "Clean wool blend overcoat.", {"Material": "Wool blend", "Water resistance": "None"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Trench Coat", "Demo Classics", "179.99", "240.00", "Classic trench.", {"Fabric": "Cotton gabardine", "Water resistance": "Moderate"}, ("color", ["Tan", "Black"]), ("size", ["S", "M", "L"])),
                            self._prod("Quilted Coat", "Demo Outdoors", "159.99", "215.00", "Quilted insulation coat.", {"Fabric": "Quilted nylon", "Water resistance": "Moderate"}, ("color", ["Olive", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Rain Coat", "Demo Outdoors", "129.99", "175.00", "Waterproof rain coat.", {"Water resistance": "High", "Closure": "Zipper"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Sherpa Lined Coat", "Demo Outdoors", "149.99", "205.00", "Warm sherpa lining.", {"Fabric": "Canvas", "Water resistance": "Light"}, ("color", ["Tan", "Olive"]), ("size", ["S", "M", "L", "XL"])),
                        ],
                    ),
                ],
            ),
            (
                "activewear",
                [
                    (
                        "active-tops",
                        [
                            self._prod("Training Tank", "Demo Active", "19.99", "28.00", "Light tank for training.", {"Fabric": "Poly knit"}, ("color", ["Black", "White"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Long Sleeve Training Top", "Demo Active", "34.99", "46.00", "Long sleeve top.", {"Fabric": "Poly knit"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Sports Bra", "Demo Active", "29.99", "40.00", "Medium support bra.", {"Fabric": "Nylon stretch"}, ("color", ["Black", "Burgundy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Half-Zip Training Pullover", "Demo Active", "49.99", "68.00", "Half-zip pullover.", {"Fabric": "Poly fleece", "Closure": "Zipper"}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L"])),
                            self._prod("Seamless Tee", "Demo Active", "27.99", "36.00", "Seamless comfort tee.", {"Fabric": "Seamless knit"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                    (
                        "active-bottoms",
                        [
                            self._prod("Training Short", "Demo Active", "29.99", "40.00", "Light training short.", {"Fabric": "Poly", "Inseam": '7"'}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Compression Short", "Demo Active", "24.99", "34.00", "Compression base short.", {"Fabric": "Nylon stretch"}, ("color", ["Black"]), ("size", ["S", "M", "L"])),
                            self._prod("Track Pant", "Demo Active", "54.99", "72.00", "Tapered track pant.", {"Fabric": "Poly knit"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L", "XL"])),
                            self._prod("Training Legging", "Demo Active", "48.99", "64.00", "Stretch legging.", {"Fabric": "Nylon stretch"}, ("color", ["Black", "Navy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Sweat Short", "Demo Active", "34.99", "46.00", "Fleece sweat short.", {"Fabric": "Fleece", "Inseam": '6"'}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                    (
                        "active-sets",
                        [
                            self._prod("Training Set: Tee + Short", "Demo Active", "64.99", "85.00", "Matching tee and short set.", {"Fabric": "Poly knit"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Yoga Set: Bra + Legging", "Demo Active", "78.99", "105.00", "Bra and legging set.", {"Fabric": "Nylon stretch"}, ("color", ["Black", "Burgundy"]), ("size", ["XS", "S", "M", "L"])),
                            self._prod("Lounge Set: Hoodie + Jogger", "Demo Active", "99.99", "135.00", "Cozy lounge set.", {"Fabric": "Fleece"}, ("color", ["Black", "Olive"]), ("size", ["S", "M", "L"])),
                            self._prod("Warm-Up Set: Jacket + Pant", "Demo Active", "119.99", "160.00", "Warm-up jacket and pant.", {"Fabric": "Poly knit"}, ("color", ["Black", "Navy"]), ("size", ["S", "M", "L"])),
                            self._prod("Recovery Set: Tee + Jogger", "Demo Active", "89.99", "120.00", "Soft recovery set.", {"Fabric": "French terry"}, ("color", ["Olive", "Navy"]), ("size", ["S", "M", "L"])),
                        ],
                    ),
                ],
            ),
        ]

        def pick_qty() -> int:
            return clamp_stock(rng.randint(3, 45))

        seeded_products = 0
        for _parent_key, children in catalog:
            for child_key, products in children:
                category = category_map[child_key]
                for spec in products:
                    p = self._ensure_product(store=store, category=category, spec=spec)
                    self._ensure_variants(product=p, spec=spec, values=values, pick_qty=pick_qty)
                    seeded_products += 1

        return seeded_products

    def _prod(
        self,
        name: str,
        brand: str,
        price: str,
        original_price: str | None,
        description: str,
        extra: dict,
        *variant_axes: tuple[str, list[str]],
    ) -> dict:
        # Keep the catalog data clean: strip legacy "Demo " branding if present.
        if isinstance(brand, str) and brand.startswith("Demo "):
            brand = brand[len("Demo ") :].strip() or brand
        return {
            "name": name,
            "brand": brand,
            "price": _money(price),
            "original_price": _money(original_price) if original_price else None,
            "description": description,
            "extra": extra,
            "variant_axes": list(variant_axes),
        }

    def _ensure_product(self, *, store: Store, category: Category, spec: dict) -> Product:
        existing = Product.objects.filter(store=store, name=spec["name"]).first()
        extra_data = {
            **(existing.extra_data if existing and isinstance(existing.extra_data, dict) else {}),
            **(spec.get("extra") or {}),
            SEED_TAG_KEY: SEED_TAG_VALUE,
        }
        if existing:
            changed = False
            if existing.category_id != category.id:
                existing.category = category
                changed = True
            if existing.brand != spec.get("brand"):
                existing.brand = spec.get("brand")
                changed = True
            if existing.price != spec.get("price"):
                existing.price = spec.get("price")
                changed = True
            if existing.original_price != spec.get("original_price"):
                existing.original_price = spec.get("original_price")
                changed = True
            if existing.description != spec.get("description"):
                existing.description = spec.get("description")
                changed = True
            if existing.extra_data != extra_data:
                existing.extra_data = extra_data
                changed = True
            if changed:
                existing.save()
            return existing

        p = Product(
            store=store,
            name=spec["name"],
            brand=spec.get("brand"),
            price=spec["price"],
            original_price=spec.get("original_price"),
            category=category,
            description=spec.get("description") or "",
            stock=0,
            stock_tracking=True,
            status=Product.Status.ACTIVE,
            is_active=True,
            extra_data=extra_data,
        )
        p.save()
        return p

    def _ensure_variants(
        self,
        *,
        product: Product,
        spec: dict,
        values: dict[str, dict[str, ProductAttributeValue]],
        pick_qty,
    ) -> None:
        axes: list[tuple[str, list[str]]] = spec.get("variant_axes") or []

        if not axes:
            # No variants: keep product-level stock with a small quantity.
            product.stock = int(pick_qty())
            product.stock_tracking = True
            product.save(update_fields=["stock", "stock_tracking"])
            return

        # Re-seed variants idempotently: if existing variant count matches the expected matrix,
        # do nothing besides refreshing inventory rows that might be missing.
        expected = 1
        for _axis, opts in axes:
            expected *= max(1, len(opts))

        current = product.variants.count()
        if current == expected:
            for v in product.variants.all():
                Inventory.objects.get_or_create(
                    product=product,
                    variant=v,
                    defaults={"quantity": int(pick_qty())},
                )
            if product.stock != 0:
                product.stock = 0
                product.save(update_fields=["stock"])
            return

        product.variants.all().delete()

        # Build cartesian product of axis options.
        combos: list[list[ProductAttributeValue]] = [[]]
        for axis_name, opts in axes:
            axis_values = [values[axis_name][v] for v in opts]
            combos = [prefix + [av] for prefix in combos for av in axis_values]

        for attrs in combos:
            v = ProductVariant.objects.create(product=product, price_override=None, is_active=True)
            Inventory.objects.get_or_create(
                product=product,
                variant=v,
                defaults={"quantity": int(pick_qty())},
            )
            for av in attrs:
                ProductVariantAttribute.objects.create(variant=v, attribute_value=av)

        # Parent stock is derived from inventory caches; keep it at 0 here.
        if product.stock != 0:
            product.stock = 0
            product.save(update_fields=["stock"])

    def _sync_stock_cache(self, store: Store) -> None:
        """Refresh stock caches from Inventory source of truth."""
        from engine.apps.inventory.cache_sync import sync_product_stock_cache

        sync_product_stock_cache(int(store.id))
