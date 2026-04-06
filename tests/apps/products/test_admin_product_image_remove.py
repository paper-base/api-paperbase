"""Admin PATCH product: remove_image clears main image; new upload replaces."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from engine.apps.products.models import Product
from engine.apps.stores.models import StoreMembership
from tests.core.test_core import (
    _ensure_default_plan,
    _make_category,
    _make_store,
    make_user,
)


def _tiny_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )


class AdminProductRemoveImageTests(TestCase):
    def setUp(self):
        _ensure_default_plan()
        self.client = APIClient()
        self.store = _make_store("ImgRm Store", "img-rm.local")
        self.user = make_user("img-rm-owner@example.com")
        StoreMembership.objects.create(
            user=self.user,
            store=self.store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        self.category = _make_category(self.store, "ImgRmCat")

    def _headers(self):
        return {"HTTP_X_STORE_PUBLIC_ID": self.store.public_id}

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
            **self._headers(),
        )
        self.assertEqual(pr.status_code, status.HTTP_201_CREATED, pr.data)
        pid = pr.data["public_id"]
        self.assertTrue(pr.data.get("image") or pr.data.get("image_url"))

        patch = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {"remove_image": "true"},
            format="multipart",
            **self._headers(),
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
            **self._headers(),
        )
        self.assertEqual(pr.status_code, status.HTTP_201_CREATED, pr.data)
        pid = pr.data["public_id"]

        patch_clear = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {"remove_image": "true"},
            format="multipart",
            **self._headers(),
        )
        self.assertEqual(patch_clear.status_code, status.HTTP_200_OK, patch_clear.data)

        patch_new = self.client.patch(
            f"/api/v1/admin/products/{pid}/",
            {
                "image": SimpleUploadedFile("b.png", png, content_type="image/png"),
            },
            format="multipart",
            **self._headers(),
        )
        self.assertEqual(patch_new.status_code, status.HTTP_200_OK, patch_new.data)
        self.assertTrue(patch_new.data.get("image") or patch_new.data.get("image_url"))
        product = Product.objects.get(public_id=pid)
        self.assertTrue(product.image and getattr(product.image, "name", ""))
