"""ProductAttribute: auto slug from name when empty; API ignores client slug."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from engine.apps.products.models import ProductAttribute
from tests.core.test_core import _ensure_default_plan, _make_store, make_user
from tests.test_helpers.jwt_auth import login_dashboard_jwt


class ProductAttributeSlugModelTests(TestCase):
    def setUp(self):
        self.store = _make_store("Attr Slug Store", "attr-slug.local")

    def test_empty_slug_generated_from_name(self):
        a = ProductAttribute(store=self.store, name="Size Chart", slug="", order=0)
        a.save()
        self.assertEqual(a.slug, "size-chart")

    def test_duplicate_name_gets_numeric_suffix(self):
        ProductAttribute.objects.create(
            store=self.store, name="Size Chart", slug="", order=0
        )
        b = ProductAttribute(store=self.store, name="Size Chart", slug="", order=1)
        b.save()
        self.assertEqual(b.slug, "size-chart-1")

    def test_explicit_slug_preserved(self):
        a = ProductAttribute(
            store=self.store, name="Demo", slug="demo-fixed", order=0
        )
        a.save()
        self.assertEqual(a.slug, "demo-fixed")

    def test_rename_does_not_change_slug(self):
        a = ProductAttribute.objects.create(
            store=self.store, name="Color", slug="", order=0
        )
        orig = a.slug
        a.name = "Colour"
        a.save()
        self.assertEqual(a.slug, orig)

    def test_slug_collision_scoped_to_store_only(self):
        store_a = _make_store("Slug Iso A", "slug-iso-a.local")
        store_b = _make_store("Slug Iso B", "slug-iso-b.local")
        ProductAttribute.objects.create(
            store=store_b, name="Other", slug="color", order=0
        )
        a = ProductAttribute(store=store_a, name="Color", slug="", order=0)
        a.save()
        self.assertEqual(a.slug, "color")


class ProductAttributeSlugAdminAPITests(TestCase):
    def setUp(self):
        _ensure_default_plan()
        self.client = APIClient()
        self.user = make_user("attr-api-owner@example.com")
        self.store = _make_store("Attr API Store", "attr-api.local", owner_email=self.user.email)
        login_dashboard_jwt(self.client, self.user.email)

    def test_post_without_slug_assigns_slug(self):
        resp = self.client.post(
            "/api/v1/admin/product-attributes/",
            {"name": "Size Chart", "order": 0},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["slug"], "size-chart")

    def test_post_collision_suffix(self):
        ProductAttribute.objects.create(
            store=self.store, name="First", slug="size-chart", order=0
        )
        resp = self.client.post(
            "/api/v1/admin/product-attributes/",
            {"name": "Size Chart", "order": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["slug"], "size-chart-1")

    def test_patch_name_keeps_slug(self):
        a = ProductAttribute.objects.create(
            store=self.store, name="Color", slug="", order=0
        )
        orig_slug = a.slug
        resp = self.client.patch(
            f"/api/v1/admin/product-attributes/{a.public_id}/",
            {"name": "Colour"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["slug"], orig_slug)
        a.refresh_from_db()
        self.assertEqual(a.name, "Colour")
        self.assertEqual(a.slug, orig_slug)

    def test_post_slug_in_body_ignored(self):
        resp = self.client.post(
            "/api/v1/admin/product-attributes/",
            {"name": "Material", "order": 0, "slug": "hacker-slug"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["slug"], "material")
