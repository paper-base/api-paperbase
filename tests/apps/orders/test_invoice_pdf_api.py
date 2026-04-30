import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from rest_framework.test import APIClient

from engine.apps.inventory.models import Inventory
from engine.apps.orders.invoice_pdf import InvoicePdfPayload
from engine.apps.orders.invoice_tasks import generate_order_invoice_pdf
from engine.apps.orders.models import Order
from engine.apps.products.models import Category, Product
from engine.apps.shipping.models import ShippingZone
from engine.apps.stores.models import Store, StoreMembership
from engine.apps.stores.services import (
    allocate_unique_store_code,
    create_store_api_key,
    normalize_store_code_base_from_name,
)
from engine.core.tenant_execution import tenant_scope_from_store
from tests.core.test_core import _ensure_default_plan, _ensure_subscription

User = get_user_model()


def _make_store(name: str) -> Store:
    base = normalize_store_code_base_from_name(name) or "T"
    email = f"{name.lower().replace(' ', '')}@example.com"
    owner = User.objects.create_user(email=email, password="pass1234", is_verified=True)
    store = Store.objects.create(
        owner=owner,
        name=name,
        code=allocate_unique_store_code(base),
        owner_name=f"{name} Owner",
        owner_email=email,
    )
    StoreMembership.objects.create(
        user=owner,
        store=store,
        role=StoreMembership.Role.OWNER,
        is_active=True,
    )
    _ensure_default_plan()
    _ensure_subscription(owner)
    return store


def _make_product(store: Store, *, name: str = "Product", price: int = 100) -> Product:
    with tenant_scope_from_store(store=store, reason="invoice test fixture"):
        category = Category.objects.create(store=store, name=f"{name} Category", slug="")
        product = Product.objects.create(
            store=store,
            category=category,
            name=name,
            price=price,
            stock=20,
            status=Product.Status.ACTIVE,
            is_active=True,
            prepayment_type=Product.PrepaymentType.NONE,
        )
        Inventory.objects.get_or_create(
            product=product,
            variant=None,
            defaults={"quantity": 20},
        )
    return product


def _api_key_client(api_key: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key}")
    return client


def _checkout_payload(product: Product, zone: ShippingZone) -> dict:
    return {
        "shipping_zone_public_id": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"product_public_id": product.public_id, "quantity": 1}],
    }


@pytest.mark.django_db
def test_invoice_endpoint_enqueues_when_missing_pdf(monkeypatch):
    store = _make_store("Invoice Queue")
    product = _make_product(store)
    zone = ShippingZone.objects.create(store=store, name="Main", is_active=True)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)
    create_resp = client.post("/api/v1/orders/", _checkout_payload(product, zone), format="json")
    public_id = create_resp.data["public_id"]

    called = {"ok": False}

    def _fake_delay(order_id, store_id):
        called["ok"] = bool(order_id) and int(store_id) == store.id

    monkeypatch.setattr("engine.apps.orders.views.generate_order_invoice_pdf.delay", _fake_delay)
    resp = client.get(f"/api/v1/orders/{public_id}/invoice/")
    assert resp.status_code == 202
    assert resp.data["status"] == "generating"
    assert called["ok"] is True


@pytest.mark.django_db
def test_invoice_status_ready_true_when_pdf_exists():
    store = _make_store("Invoice Ready")
    product = _make_product(store)
    zone = ShippingZone.objects.create(store=store, name="Main", is_active=True)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)
    create_resp = client.post("/api/v1/orders/", _checkout_payload(product, zone), format="json")
    order = Order.objects.get(public_id=create_resp.data["public_id"], store=store)
    order.pdf_file.save("invoice_ready.pdf", ContentFile(b"%PDF-1.4 ready"), save=True)

    resp = client.get(f"/api/v1/orders/{order.public_id}/invoice/status/")
    assert resp.status_code == 200
    assert resp.data["ready"] is True
    assert resp.data["url"]


@pytest.mark.django_db
def test_invoice_status_is_store_isolated():
    store_a = _make_store("Invoice Store A")
    store_b = _make_store("Invoice Store B")
    product = _make_product(store_a)
    zone = ShippingZone.objects.create(store=store_a, name="Main", is_active=True)
    _row_a, key_a = create_store_api_key(store_a, name="frontend-a")
    _row_b, key_b = create_store_api_key(store_b, name="frontend-b")
    client_a = _api_key_client(key_a)
    client_b = _api_key_client(key_b)
    create_resp = client_a.post("/api/v1/orders/", _checkout_payload(product, zone), format="json")
    public_id = create_resp.data["public_id"]

    resp = client_b.get(f"/api/v1/orders/{public_id}/invoice/status/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_invoice_storage_path_is_namespaced_by_store_and_order():
    store = _make_store("Invoice Path")
    product = _make_product(store)
    zone = ShippingZone.objects.create(store=store, name="Main", is_active=True)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)
    create_resp = client.post("/api/v1/orders/", _checkout_payload(product, zone), format="json")
    order = Order.objects.get(public_id=create_resp.data["public_id"], store=store)
    order.pdf_file.save("invoice.pdf", ContentFile(b"%PDF-1.4 path"), save=True)

    assert f"tenants/{store.public_id}/store_invoices/orders/{order.id}/" in order.pdf_file.name
    assert f"invoice_{order.order_number}" in order.pdf_file.name


@pytest.mark.django_db
def test_generate_order_invoice_task_rejects_store_mismatch(monkeypatch):
    store_a = _make_store("Invoice Task A")
    store_b = _make_store("Invoice Task B")
    product = _make_product(store_a)
    zone = ShippingZone.objects.create(store=store_a, name="Main", is_active=True)
    _row, key = create_store_api_key(store_a, name="frontend")
    client = _api_key_client(key)
    create_resp = client.post("/api/v1/orders/", _checkout_payload(product, zone), format="json")
    order = Order.objects.get(public_id=create_resp.data["public_id"], store=store_a)

    def _fake_render(*, order):
        return InvoicePdfPayload(order=order, content=b"%PDF-1.4 task", filename="invoice.pdf")

    # Should fail closed and avoid writing a file for wrong store id.
    from engine.apps.orders import invoice_tasks

    monkeypatch.setattr(invoice_tasks, "render_order_invoice_pdf", _fake_render)
    generate_order_invoice_pdf.run(str(order.id), int(store_b.id))

    order.refresh_from_db()
    assert not order.pdf_file
