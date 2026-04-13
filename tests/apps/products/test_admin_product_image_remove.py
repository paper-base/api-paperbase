"""Admin PATCH product: remove_image clears main image; new upload replaces."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from engine.apps.products.models import Product
from tests.core.test_core import (
    _ensure_default_plan,
    _make_category,
    _make_store,
    make_user,
)
from tests.test_helpers.jwt_auth import login_dashboard_jwt


def _tiny_png() -> bytes:
    """Minimal valid PNG bytes (Pillow) so django validates the upload."""
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (2, 2), color=(200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


class AdminProductRemoveImageTests(TestCase):
    def setUp(self):
        _ensure_default_plan()
        self.client = APIClient()
        self.user = make_user("img-rm-owner@example.com")
        self.store = _make_store("ImgRm Store", "img-rm.local", owner_email=self.user.email)
        login_dashboard_jwt(self.client, self.user.email)
        self.category = _make_category(self.store, "ImgRmCat")

    def test_patch_remove_image_true_clears_main_image(self):
        png = _tiny_png()
        up = SimpleUploadedFile("one.png", png, content_type="image/png")
        pr = self.client.post(
            "/api/v1/admin/products/",
            {
                "name": "Has Image",
                "price": "11.00",
                "category": self.category.public_id,
                "is_active": "true",
                "description": "",
                "image": up,
            },
            format="multipart",
        )
        self.assertEqual(pr.status_code, status.HTTP_201_CREATED, pr.data)
        pid = pr.data["public_id"]
        self.assertTrue(pr.data.get("image") or pr.data.get("image_url"))

        patch = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {"remove_image": "true"},
            format="multipart",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)
        self.assertFalse(patch.data.get("image"))
        product = Product.objects.get(public_id=pid)
        self.assertFalse(product.image or getattr(product.image, "name", ""))

    def test_patch_new_image_replaces_after_remove(self):
        png = _tiny_png()
        pr = self.client.post(
            "/api/v1/admin/products/",
            {
                "name": "Replace Me",
                "price": "12.00",
                "category": self.category.public_id,
                "is_active": "true",
                "description": "",
                "image": SimpleUploadedFile("a.png", png, content_type="image/png"),
            },
            format="multipart",
        )
        self.assertEqual(pr.status_code, status.HTTP_201_CREATED, pr.data)
        pid = pr.data["public_id"]

        patch_clear = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {"remove_image": "true"},
            format="multipart",
        )
        self.assertEqual(patch_clear.status_code, status.HTTP_200_OK, patch_clear.data)

        patch_new = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {
                "image": SimpleUploadedFile("b.png", png, content_type="image/png"),
            },
            format="multipart",
        )
        self.assertEqual(patch_new.status_code, status.HTTP_200_OK, patch_new.data)
        self.assertTrue(patch_new.data.get("image") or patch_new.data.get("image_url"))
        product = Product.objects.get(public_id=pid)
        self.assertTrue(product.image and getattr(product.image, "name", ""))

    def test_sequential_main_image_uploads_use_distinct_storage_keys(self):
        png = _tiny_png()
        pr = self.client.post(
            "/api/v1/admin/products/",
            {
                "name": "Key Uniq",
                "price": "13.00",
                "category": self.category.public_id,
                "is_active": "true",
                "description": "",
                "image": SimpleUploadedFile("a.png", png, content_type="image/png"),
            },
            format="multipart",
        )
        self.assertEqual(pr.status_code, status.HTTP_201_CREATED, pr.data)
        pid = pr.data["public_id"]
        first_key = Product.objects.get(public_id=pid).image.name

        patch = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {"image": SimpleUploadedFile("b.png", png, content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK, patch.data)
        second_key = Product.objects.get(public_id=pid).image.name
        self.assertNotEqual(first_key, second_key)
