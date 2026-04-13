"""Admin POST /admin/products/reorder/ — tenant- and category-scoped display_order."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from tests.core.test_core import (
    _ensure_default_plan,
    _make_category,
    _make_product,
    _make_store,
    make_user,
)
from tests.test_helpers.jwt_auth import login_dashboard_jwt


class AdminProductReorderTests(TestCase):
    def setUp(self):
        _ensure_default_plan()
        self.client = APIClient()
        self.user = make_user("reorder-owner@example.com")
        self.store = _make_store("Reorder Store", "reorder.local", owner_email=self.user.email)
        login_dashboard_jwt(self.client, self.user.email)
        self.cat_a = _make_category(self.store, "CatA")
        self.cat_b = _make_category(self.store, "CatB")
        self.other_store = _make_store("Other", "other.local", owner_email="other@example.com")
        self.cat_other = _make_category(self.other_store, "OtherCat")

    def test_reorder_updates_display_order_within_category(self):
        p0 = _make_product(self.store, self.cat_a, name="P0")
        p1 = _make_product(self.store, self.cat_a, name="P1")
        p2 = _make_product(self.store, self.cat_a, name="P2")

        resp = self.client.post(
            "/api/v1/admin/products/reorder/",
            {
                "category_public_id": self.cat_a.public_id,
                "product_public_ids": [p2.public_id, p0.public_id, p1.public_id],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        p0.refresh_from_db()
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p2.display_order, 0)
        self.assertEqual(p0.display_order, 1)
        self.assertEqual(p1.display_order, 2)

    def test_reorder_rejects_incomplete_id_list(self):
        _make_product(self.store, self.cat_a, name="P0")
        p1 = _make_product(self.store, self.cat_a, name="P1")

        resp = self.client.post(
            "/api/v1/admin/products/reorder/",
            {
                "category_public_id": self.cat_a.public_id,
                "product_public_ids": [p1.public_id],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)

    def test_reorder_rejects_mixed_category(self):
        pa = _make_product(self.store, self.cat_a, name="PA")
        pb = _make_product(self.store, self.cat_b, name="PB")

        resp = self.client.post(
            "/api/v1/admin/products/reorder/",
            {
                "category_public_id": self.cat_a.public_id,
                "product_public_ids": [pa.public_id, pb.public_id],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)

    def test_reorder_ignores_other_store_product_id(self):
        p_own = _make_product(self.store, self.cat_a, name="Own")
        p_other = _make_product(self.other_store, self.cat_other, name="Other")

        resp = self.client.post(
            "/api/v1/admin/products/reorder/",
            {
                "category_public_id": self.cat_a.public_id,
                "product_public_ids": [p_own.public_id, p_other.public_id],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
