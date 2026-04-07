"""Admin API: inactive variants excluded by default; include_inactive opt-in."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from engine.apps.inventory.cache_sync import sync_product_stock_cache
from engine.apps.inventory.models import Inventory
from engine.apps.products.models import Product, ProductVariant
from engine.core.tenant_execution import tenant_scope_from_store
from tests.core.test_core import _ensure_default_plan, _make_category, _make_store, make_user
from tests.test_helpers.jwt_auth import login_dashboard_jwt


class InactiveVariantEnforcementTests(TestCase):
    def setUp(self):
        _ensure_default_plan()
        self.client = APIClient()
        self.user = make_user("inactive-var-owner@example.com")
        self.store = _make_store("Inactive Var Store", "inactive-var.local", owner_email=self.user.email)
        login_dashboard_jwt(self.client, self.user.email)
        self.category = _make_category(self.store, "InactiveVarCat")

    def _create_variant_product(self):
        pr = self.client.post(
            "/api/v1/admin/products/",
            {
                "name": "Two Variant Product",
                "price": "10.00",
                "category": self.category.public_id,
                "is_active": True,
                "description": "",
            },
            format="json",
        )
        self.assertEqual(pr.status_code, status.HTTP_201_CREATED, pr.data)
        product_pid = pr.data["public_id"]
        active = self.client.post(
            "/api/v1/admin/product-variants/",
            {
                "product_public_id": product_pid,
                "attribute_value_public_ids": [],
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(active.status_code, status.HTTP_201_CREATED, active.data)
        inactive = self.client.post(
            "/api/v1/admin/product-variants/",
            {
                "product_public_id": product_pid,
                "attribute_value_public_ids": [],
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(inactive.status_code, status.HTTP_201_CREATED, inactive.data)
        return product_pid, active.data["public_id"], inactive.data["public_id"]

    def test_variant_list_defaults_to_active_only(self):
        product_pid, active_pid, inactive_pid = self._create_variant_product()
        r = self.client.get(
            "/api/v1/admin/product-variants/",
            {"product_public_id": product_pid},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        ids = {row["public_id"] for row in r.data["results"]}
        self.assertIn(active_pid, ids)
        self.assertNotIn(inactive_pid, ids)

    def test_variant_list_include_inactive_shows_all(self):
        product_pid, active_pid, inactive_pid = self._create_variant_product()
        r = self.client.get(
            "/api/v1/admin/product-variants/",
            {"product_public_id": product_pid, "include_inactive": "true"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        ids = {row["public_id"] for row in r.data["results"]}
        self.assertIn(active_pid, ids)
        self.assertIn(inactive_pid, ids)

    def test_retrieve_inactive_variant_by_public_id(self):
        _, _, inactive_pid = self._create_variant_product()
        r = self.client.get(
            f"/api/v1/admin/product-variants/{inactive_pid}/",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(r.data["is_active"])

    def test_inventory_list_hides_inactive_variant_rows_by_default(self):
        product_pid, _, inactive_pid = self._create_variant_product()
        with tenant_scope_from_store(store=self.store, reason="test"):
            v = ProductVariant.objects.get(public_id=inactive_pid)
            inv = Inventory.objects.get(product__public_id=product_pid, variant=v)
            inv.quantity = 5
            inv.save(update_fields=["quantity"])

        r = self.client.get("/api/v1/admin/inventory/")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        inv_ids = {row.get("public_id") for row in r.data["results"]}
        self.assertNotIn(inv.public_id, inv_ids)

        r2 = self.client.get(
            "/api/v1/admin/inventory/",
            {"include_inactive": "true"},
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)
        inv_ids2 = {row.get("public_id") for row in r2.data["results"]}
        self.assertIn(inv.public_id, inv_ids2)

    def test_sync_product_stock_cache_ignores_inactive_variant_inventory(self):
        product_pid, active_pid, inactive_pid = self._create_variant_product()
        with tenant_scope_from_store(store=self.store, reason="test"):
            product = Product.objects.get(public_id=product_pid)
            inv_active = Inventory.objects.get(
                product=product, variant=ProductVariant.objects.get(public_id=active_pid)
            )
            inv_inactive = Inventory.objects.get(
                product=product, variant=ProductVariant.objects.get(public_id=inactive_pid)
            )
            inv_active.quantity = 3
            inv_active.save(update_fields=["quantity"])
            inv_inactive.quantity = 99
            inv_inactive.save(update_fields=["quantity"])

            sync_product_stock_cache(self.store.id)
            product.refresh_from_db()
            self.assertEqual(product.stock, 3)
