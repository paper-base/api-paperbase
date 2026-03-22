"""Public banner list: tenant isolation and scheduling."""

from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from engine.apps.banners.models import Banner
from engine.apps.stores.models import Domain, Store

# Minimal valid 1x1 PNG
_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_store(name: str, host: str) -> Store:
    store = Store.objects.create(
        name=name,
        domain=None,
        owner_name=f"{name} Owner",
        owner_email=f"owner@{host}",
    )
    Domain.objects.filter(store=store, is_custom=False).update(
        domain=host.strip().lower().split(":", 1)[0]
    )
    return store


def _make_banner(store: Store, *, title: str, order: int = 0, is_active: bool = True) -> Banner:
    return Banner.objects.create(
        store=store,
        title=title,
        image=ContentFile(_MIN_PNG, name="t.png"),
        is_active=is_active,
        order=order,
    )


class PublicBannerTenantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.store_a = _make_store("Store A", "store-a.local")
        self.store_b = _make_store("Store B", "store-b.local")
        self.banner_a = _make_banner(self.store_a, title="Banner A", order=1)
        self.banner_b = _make_banner(self.store_b, title="Banner B", order=2)

    def test_banner_list_scoped_to_host(self):
        r = self.client.get("/api/v1/banners/", HTTP_HOST="store-a.local")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        ids = {row["public_id"] for row in data}
        self.assertIn(self.banner_a.public_id, ids)
        self.assertNotIn(self.banner_b.public_id, ids)

    def test_banner_list_without_tenant_forbidden(self):
        r = self.client.get("/api/v1/banners/")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json().get("detail"), "Unknown tenant host.")

    def test_inactive_banner_excluded(self):
        _make_banner(self.store_a, title="Hidden", is_active=False)
        r = self.client.get("/api/v1/banners/", HTTP_HOST="store-a.local")
        self.assertEqual(r.status_code, 200)
        titles = {row["title"] for row in r.json()}
        self.assertNotIn("Hidden", titles)

    def test_future_start_at_excluded(self):
        b = _make_banner(self.store_a, title="Future")
        b.start_at = timezone.now() + timedelta(days=7)
        b.save(update_fields=["start_at"])
        r = self.client.get("/api/v1/banners/", HTTP_HOST="store-a.local")
        self.assertEqual(r.status_code, 200)
        titles = {row["title"] for row in r.json()}
        self.assertNotIn("Future", titles)

    def test_past_end_at_excluded(self):
        b = _make_banner(self.store_a, title="Expired")
        b.end_at = timezone.now() - timedelta(days=1)
        b.save(update_fields=["end_at"])
        r = self.client.get("/api/v1/banners/", HTTP_HOST="store-a.local")
        self.assertEqual(r.status_code, 200)
        titles = {row["title"] for row in r.json()}
        self.assertNotIn("Expired", titles)

    def test_ordering_by_order_field(self):
        _make_banner(self.store_a, title="Second", order=10)
        _make_banner(self.store_a, title="First", order=0)
        r = self.client.get("/api/v1/banners/", HTTP_HOST="store-a.local")
        self.assertEqual(r.status_code, 200)
        titles = [row["title"] for row in r.json()]
        self.assertLess(titles.index("First"), titles.index("Second"))


class PublicBannerNoAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.store = _make_store("S", "only.local")
        _make_banner(self.store, title="Public")

    def test_no_authentication_required(self):
        r = self.client.get("/api/v1/banners/", HTTP_HOST="only.local")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
