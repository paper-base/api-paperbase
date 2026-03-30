"""Production hardening invariants for variant SKUs (format unchanged)."""

from __future__ import annotations

import threading
import unittest

from django.db import connection
from django.test import TestCase, TransactionTestCase

from engine.apps.inventory.models import Inventory
from engine.apps.products.models import Product, ProductVariant
from engine.apps.products.product_search import filter_products_by_prioritized_search
from engine.apps.stores.models import StoreMembership
from engine.core.tenant_execution import tenant_scope_from_store
from tests.core.test_core import (
    _make_category,
    _make_order,
    _make_order_item,
    _make_store,
    make_user,
)


class StoreCodeTests(TestCase):
    def test_code_set_on_create_and_stable_when_slug_changes(self):
        store = _make_store("Code Test", "code-test.example.com")
        self.assertTrue(store.code)
        self.assertLessEqual(len(store.code), 10)
        self.assertEqual(store.code, store.code.upper())
        old_code = store.code
        store.name = "Renamed Store"
        store.slug = "renamed-store-unique"
        store.save()
        store.refresh_from_db()
        self.assertEqual(store.code, old_code)


class VariantSkuInvariantTests(TestCase):
    def setUp(self):
        self.store = _make_store("SKU Inv", "sku-inv.example.com")
        self.user = make_user("sku-inv@example.com")
        StoreMembership.objects.create(
            user=self.user,
            store=self.store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )
        self.category = _make_category(self.store, "SkuCat")
        with tenant_scope_from_store(store=self.store, reason="test"):
            self.product = Product.objects.create(
                store=self.store,
                category=self.category,
                name="Widget",
                price=10,
                stock=0,
                status=Product.Status.ACTIVE,
                is_active=True,
            )

    def test_sku_nonempty_and_prefix_on_create(self):
        with tenant_scope_from_store(store=self.store, reason="test"):
            v = ProductVariant.objects.create(product=self.product, is_active=True)
        self.assertTrue(v.sku)
        self.assertTrue(v.sku.startswith("SKU-"))
        self.assertIn(self.store.code, v.sku)

    def test_sku_immutable_on_update_via_orm(self):
        with tenant_scope_from_store(store=self.store, reason="test"):
            v = ProductVariant.objects.create(product=self.product, is_active=True)
            old = v.sku
            v.sku = "SKU-MANUAL-OVERRIDE"
            v.save()
        v.refresh_from_db()
        self.assertEqual(v.sku, old)

    def test_many_sequential_creates_unique_skus(self):
        skus = set()
        for _ in range(15):
            with tenant_scope_from_store(store=self.store, reason="test"):
                v = ProductVariant.objects.create(product=self.product, is_active=True)
            self.assertNotIn(v.sku, skus)
            skus.add(v.sku)


class ParallelVariantSkuStressTests(TransactionTestCase):
    """
    High-concurrency collision stress (real DB locks). Skipped on SQLite; run CI with PostgreSQL.
    """

    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != "postgresql":
            raise unittest.SkipTest(
                "Parallel SKU stress test requires PostgreSQL (e.g. CI with Postgres-backed settings)."
            )

    def test_concurrent_four_threads_no_duplicate_skus(self):
        store = _make_store("Conc SKU", "conc-sku.example.com")
        cat = _make_category(store, "CCat")
        with tenant_scope_from_store(store=store, reason="test"):
            product = Product.objects.create(
                store=store,
                category=cat,
                name="Concurrent",
                price=1,
                stock=0,
                status=Product.Status.ACTIVE,
                is_active=True,
            )

        errors: list[BaseException] = []
        barrier = threading.Barrier(4)

        def worker():
            from django.db import close_old_connections

            close_old_connections()
            try:
                barrier.wait()
                with tenant_scope_from_store(store=store, reason="test"):
                    ProductVariant.objects.create(product=product, is_active=True)
            except BaseException as e:
                errors.append(e)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(errors, [], errors)
        skus = list(ProductVariant.objects.filter(product=product).values_list("sku", flat=True))
        self.assertEqual(len(skus), len(set(skus)))
        self.assertEqual(len(skus), 4)

    def test_parallel_creates_no_duplicates_repeated(self):
        n_workers = 100
        n_rounds = 4
        for round_i in range(n_rounds):
            with self.subTest(round=round_i):
                store = _make_store(f"Stress {round_i}", f"stress-{round_i}.example.com")
                cat = _make_category(store, f"SCat{round_i}")
                with tenant_scope_from_store(store=store, reason="test"):
                    product = Product.objects.create(
                        store=store,
                        category=cat,
                        name=f"Concurrent {round_i}",
                        price=1,
                        stock=0,
                        status=Product.Status.ACTIVE,
                        is_active=True,
                    )

                errors: list[BaseException] = []
                barrier = threading.Barrier(n_workers)

                def worker():
                    from django.db import close_old_connections

                    close_old_connections()
                    try:
                        barrier.wait()
                        with tenant_scope_from_store(store=store, reason="test"):
                            ProductVariant.objects.create(product=product, is_active=True)
                    except BaseException as e:
                        errors.append(e)
                    finally:
                        close_old_connections()

                threads = [threading.Thread(target=worker) for _ in range(n_workers)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=120)
                self.assertEqual(errors, [], errors)
                variants = ProductVariant.objects.filter(product=product)
                self.assertEqual(variants.count(), n_workers)
                skus = list(variants.values_list("sku", flat=True))
                self.assertEqual(len(skus), len(set(skus)))


class SearchPrioritizationTests(TestCase):
    def test_name_match_ranks_before_sku_prefix_only(self):
        store = _make_store("Search Pri", "search-pri.example.com")
        cat = _make_category(store, "SCat")
        with tenant_scope_from_store(store=store, reason="test"):
            p_name = Product.objects.create(
                store=store,
                category=cat,
                name="UniqueRedHammer",
                price=5,
                stock=0,
                status=Product.Status.ACTIVE,
                is_active=True,
            )
            p_sku_only = Product.objects.create(
                store=store,
                category=cat,
                name="ZZZ Obscure",
                price=5,
                stock=0,
                status=Product.Status.ACTIVE,
                is_active=True,
            )
            with tenant_scope_from_store(store=store, reason="test"):
                v = ProductVariant.objects.create(product=p_sku_only, is_active=True)
        # Force a predictable SKU prefix for the second product (immutable save prevents direct set)
        from django.db import connection

        with connection.cursor() as c:
            c.execute(
                "UPDATE products_productvariant SET sku = %s WHERE id = %s",
                [f"SKU-{store.code}-1111111-999999", v.pk],
            )

        qs = Product.objects.filter(store=store)
        with tenant_scope_from_store(store=store, reason="test"):
            ranked = list(
                filter_products_by_prioritized_search(qs, "UniqueRed").values_list("pk", flat=True)
            )
            self.assertEqual(ranked[0], p_name.pk)

            ranked2 = list(
                filter_products_by_prioritized_search(qs, f"SKU-{store.code}-1111111").values_list(
                    "pk", flat=True
                )
            )
            self.assertEqual(ranked2[0], p_sku_only.pk)


class OrderVariantIdentityTests(TestCase):
    def test_order_item_links_variant_id_not_sku(self):
        store = _make_store("Ord SKU", "ord-sku.example.com")
        cat = _make_category(store, "OCat")
        with tenant_scope_from_store(store=store, reason="test"):
            product = Product.objects.create(
                store=store,
                category=cat,
                name="Sold",
                price=3,
                stock=0,
                status=Product.Status.ACTIVE,
                is_active=True,
            )
            variant = ProductVariant.objects.create(product=product, is_active=True)
        order = _make_order(store)
        item = _make_order_item(order, product, variant=variant)
        self.assertEqual(item.variant_id, variant.id)
        from django.db import connection

        with connection.cursor() as c:
            c.execute(
                "UPDATE products_productvariant SET sku = %s WHERE id = %s",
                ["SKU-CHANGED-1-1", variant.pk],
            )
        item.refresh_from_db()
        self.assertEqual(item.variant_id, variant.id)
        variant.refresh_from_db()
        self.assertEqual(variant.sku, "SKU-CHANGED-1-1")
