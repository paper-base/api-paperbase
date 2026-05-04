"""Tenant isolation and auth behavior for /api/v1/theming/."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from engine.apps.billing.models import Plan
from engine.apps.billing.services import activate_subscription
from engine.apps.stores.models import Store, StoreMembership
from engine.apps.stores.services import allocate_unique_store_code, create_store_api_key, normalize_store_code_base_from_name
from engine.apps.theming.cache import theme_cache_key
from engine.apps.theming.models import StorefrontTheme

User = get_user_model()


def _make_user(email: str):
    return User.objects.create_user(email=email, password="pass1234", is_verified=True)


def _make_store(owner: User, name: str, domain: str) -> Store:
    base = normalize_store_code_base_from_name(name) or "T"
    store = Store.objects.create(
        owner=owner,
        name=name,
        code=allocate_unique_store_code(base),
        owner_name=f"{name} Owner",
        owner_email=owner.email,
    )
    StoreMembership.objects.get_or_create(
        user=owner,
        store=store,
        defaults={"role": StoreMembership.Role.OWNER, "is_active": True},
    )
    return store


def _ensure_subscription(user: User):
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
        plan.save(update_fields=["is_default"])
    activate_subscription(user, plan, source="manual", amount=0, provider="manual")


def _auth_jwt(client: APIClient, email: str, *, store_public_id: str | None = None):
    extra = {}
    if store_public_id:
        extra["HTTP_X_STORE_PUBLIC_ID"] = store_public_id
    resp = client.post(
        "/api/v1/auth/token/",
        {"email": email, "password": "pass1234"},
        format="json",
        **extra,
    )
    assert resp.status_code == 200, resp.content
    token = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return token


class ThemingIsolationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.owner_a = _make_user("owner-a@theming.test")
        self.owner_b = _make_user("owner-b@theming.test")
        self.store_a = _make_store(self.owner_a, "Store A", "a.test")
        self.store_b = _make_store(self.owner_b, "Store B", "b.test")

        self.theme_a = StorefrontTheme.objects.get(store=self.store_a)
        self.theme_b = StorefrontTheme.objects.get(store=self.store_b)
        self.theme_a.palette = "ivory"
        self.theme_a.save(update_fields=["palette"])
        self.theme_b.palette = "sage"
        self.theme_b.save(update_fields=["palette"])

        _ensure_subscription(self.owner_a)
        _ensure_subscription(self.owner_b)

        self.pk_a, _ = create_store_api_key(store=self.store_a, name="pub-a")
        self.pk_b, _ = create_store_api_key(store=self.store_b, name="pub-b")

    def test_jwt_user_a_sees_only_store_a_theme(self):
        _auth_jwt(self.client, self.owner_a.email, store_public_id=self.store_a.public_id)
        resp = self.client.get("/api/v1/theming/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["palette"], "ivory")
        self.assertEqual(resp.data["card_variant"], "classic")

    def test_jwt_user_b_sees_only_store_b_theme(self):
        _auth_jwt(self.client, self.owner_b.email, store_public_id=self.store_b.public_id)
        resp = self.client.get("/api/v1/theming/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["palette"], "sage")
        self.assertEqual(resp.data["card_variant"], "classic")

    def test_patch_card_variant_jwt(self):
        _auth_jwt(self.client, self.owner_a.email, store_public_id=self.store_a.public_id)
        resp = self.client.patch("/api/v1/theming/", {"card_variant": "shelf"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["card_variant"], "shelf")
        self.theme_a.refresh_from_db()
        self.assertEqual(self.theme_a.card_variant, "shelf")

    def test_patch_invalid_card_variant_returns_400(self):
        _auth_jwt(self.client, self.owner_a.email, store_public_id=self.store_a.public_id)
        resp = self.client.patch("/api/v1/theming/", {"card_variant": "nope"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_patch_with_api_key_returns_403(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.pk_a}")
        resp = self.client.patch("/api/v1/theming/", {"palette": "arctic"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_get_returns_401(self):
        self.client.credentials()
        resp = self.client.get("/api/v1/theming/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cache_keys_differ_per_tenant_public_id(self):
        self.assertNotEqual(
            theme_cache_key(self.store_a.public_id),
            theme_cache_key(self.store_b.public_id),
        )
