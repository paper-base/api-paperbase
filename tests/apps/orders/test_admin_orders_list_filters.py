"""Admin order list query filters and search."""

from django.test import TestCase
from rest_framework.test import APIClient

from engine.apps.orders.models import Order

from tests.core.test_core import (
    _default_shipping_zone,
    _ensure_default_plan,
    _make_order,
    _make_store,
    make_user,
)
from tests.test_helpers.jwt_auth import login_dashboard_jwt


class AdminOrdersListFiltersTests(TestCase):
    def setUp(self):
        _ensure_default_plan()
        self.client = APIClient()
        self.user = make_user("orders-filters-admin@example.com")
        self.store = _make_store(
            "Orders Filters Store",
            "orders-filters.local",
            owner_email=self.user.email,
        )
        self.zone = _default_shipping_zone(self.store)
        self.order_none = _make_order(
            self.store,
            "a@example.com",
            shipping_zone=self.zone,
            district="Dhaka",
            shipping_address="Addr A",
            payment_status=Order.PaymentStatus.NONE,
            transaction_id="",
        )
        self.order_submitted = _make_order(
            self.store,
            "b@example.com",
            shipping_zone=self.zone,
            district="Dhaka",
            shipping_address="Addr B",
            payment_status=Order.PaymentStatus.SUBMITTED,
            transaction_id="TX-12345",
        )

    def _auth(self):
        login_dashboard_jwt(self.client, self.user.email)

    def _list_ids(self, resp):
        return {row["public_id"] for row in resp.data["results"]}

    def test_filter_payment_status(self):
        self._auth()
        r_all = self.client.get("/api/v1/admin/orders/")
        self.assertEqual(r_all.status_code, 200)
        self.assertEqual(len(self._list_ids(r_all)), 2)

        r_none = self.client.get(
            "/api/v1/admin/orders/",
            {"payment_status": Order.PaymentStatus.NONE},
        )
        self.assertEqual(r_none.status_code, 200)
        ids = self._list_ids(r_none)
        self.assertEqual(ids, {self.order_none.public_id})

        r_sub = self.client.get(
            "/api/v1/admin/orders/",
            {"payment_status": Order.PaymentStatus.SUBMITTED},
        )
        self.assertEqual(r_sub.status_code, 200)
        self.assertEqual(self._list_ids(r_sub), {self.order_submitted.public_id})

    def test_search_matches_transaction_id(self):
        self._auth()
        r = self.client.get("/api/v1/admin/orders/", {"search": "TX-123"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._list_ids(r), {self.order_submitted.public_id})
