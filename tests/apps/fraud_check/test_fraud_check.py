from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from engine.apps.billing.models import Plan
from engine.apps.billing.services import activate_subscription
from engine.apps.fraud_check.models import FraudCheckLog
from engine.apps.stores.models import Store, StoreMembership
from engine.apps.stores.services import allocate_unique_store_code, normalize_store_code_base_from_name
from engine.core.tenant_execution import tenant_scope_from_store


User = get_user_model()


def _make_user(email: str, password: str = "pass1234"):
    return User.objects.create_user(email=email, password=password, is_verified=True)


def _set_default_plan():
    Plan.objects.all().update(is_default=False)
    plan = Plan.objects.filter(name="basic").first()
    if not plan:
        plan = Plan.objects.create(
            name="basic",
            price="0.00",
            billing_cycle="monthly",
            is_active=True,
            is_default=True,
            features={"limits": {"max_products": 100}, "features": {}},
        )
    else:
        plan.is_default = True
        plan.is_active = True
        plan.save(update_fields=["is_default", "is_active"])
    return plan


def _make_store(name: str, owner):
    base = normalize_store_code_base_from_name(name) or "T"
    store = Store.objects.create(
        owner=owner,
        name=name,
        code=allocate_unique_store_code(base),
        owner_name=f"{name} Owner",
        owner_email=owner.email,
        is_active=True,
    )
    StoreMembership.objects.get_or_create(
        user=owner,
        store=store,
        defaults={"role": StoreMembership.Role.OWNER, "is_active": True},
    )
    return store


def _auth_owner(client: APIClient, *, email: str, password: str, store_public_id: str):
    resp = client.post(
        "/api/v1/auth/token/",
        {"email": email, "password": password},
        format="json",
        HTTP_X_STORE_PUBLIC_ID=store_public_id,
    )
    assert resp.status_code == 200, getattr(resp, "data", None)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")


class FraudCheckEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.plan = _set_default_plan()

        self.owner_a = _make_user("owner-a@example.com")
        activate_subscription(self.owner_a, self.plan)
        self.store_a = _make_store("Store A", self.owner_a)

        self.owner_b = _make_user("owner-b@example.com")
        activate_subscription(self.owner_b, self.plan)
        self.store_b = _make_store("Store B", self.owner_b)

    def test_invalid_phone_rejected(self):
        _auth_owner(
            self.client,
            email=self.owner_a.email,
            password="pass1234",
            store_public_id=self.store_a.public_id,
        )
        resp = self.client.post("/api/v1/fraud-check/", {"phone": "123"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("phone", resp.data)

    @patch("engine.apps.fraud_check.services.requests.post")
    def test_cache_hit_skips_api(self, mock_post):
        with tenant_scope_from_store(store=self.store_a, reason="test fraud check cache hit"):
            log = FraudCheckLog.objects.create(
                store=self.store_a,
                phone_number="01712345678",
                normalized_phone="01712345678",
                response_json={"ok": True, "source": "db"},
                status=FraudCheckLog.Status.SUCCESS,
            )
            log.checked_at = timezone.now()
            log.save(update_fields=["checked_at"])

        _auth_owner(
            self.client,
            email=self.owner_a.email,
            password="pass1234",
            store_public_id=self.store_a.public_id,
        )
        resp = self.client.post("/api/v1/fraud-check/", {"phone": "01712345678"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("cached"))
        self.assertEqual(resp.data["response"].get("source"), "db")
        mock_post.assert_not_called()

    @override_settings(STORE_DAILY_LIMIT=1, FRAUD_API_KEY="test_key")
    @patch("engine.apps.fraud_check.services.requests.post")
    def test_limit_exceeded_returns_429_and_skips_api(self, mock_post):
        with tenant_scope_from_store(store=self.store_a, reason="seed fraud check usage"):
            FraudCheckLog.objects.create(
                store=self.store_a,
                phone_number="01700000000",
                normalized_phone="01700000000",
                response_json={"seed": True},
                status=FraudCheckLog.Status.SUCCESS,
            )

        _auth_owner(
            self.client,
            email=self.owner_a.email,
            password="pass1234",
            store_public_id=self.store_a.public_id,
        )
        resp = self.client.post("/api/v1/fraud-check/", {"phone": "01712345678"}, format="json")
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.data.get("limit_exceeded"), "store_daily")
        mock_post.assert_not_called()

    @patch("engine.apps.fraud_check.services.requests.post")
    def test_multi_tenant_isolation_cache_lookup(self, mock_post):
        with tenant_scope_from_store(store=self.store_a, reason="seed store a fraud cache"):
            FraudCheckLog.objects.create(
                store=self.store_a,
                phone_number="01799999999",
                normalized_phone="01799999999",
                response_json={"store": "A"},
                status=FraudCheckLog.Status.SUCCESS,
            )
        with tenant_scope_from_store(store=self.store_b, reason="seed store b fraud cache"):
            FraudCheckLog.objects.create(
                store=self.store_b,
                phone_number="01799999999",
                normalized_phone="01799999999",
                response_json={"store": "B"},
                status=FraudCheckLog.Status.SUCCESS,
            )

        _auth_owner(
            self.client,
            email=self.owner_a.email,
            password="pass1234",
            store_public_id=self.store_a.public_id,
        )
        resp = self.client.post("/api/v1/fraud-check/", {"phone": "01799999999"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("cached"))
        self.assertEqual(resp.data["response"].get("store"), "A")
        mock_post.assert_not_called()

