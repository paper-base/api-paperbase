"""Tests for the prepayment order lifecycle.

Covers:
- cart prepayment resolver (strongest-wins ranking)
- order creation sets the correct initial status per cart composition
- payment submission endpoint (happy path + state guards + tenant isolation)
- admin verify-payment action (valid and invalid branches)
- interplay with `apply_order_status_change` (blocks premature confirmation)
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from engine.apps.inventory.models import Inventory
from engine.apps.orders.models import Order, StockRestoreLog
from engine.apps.orders.services import (
    apply_order_status_change,
    apply_payment_verification,
    resolve_cart_prepayment_type,
    submit_order_payment,
)
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
    # Storefront API-key views require the owner to have an active subscription.
    _ensure_default_plan()
    _ensure_subscription(owner)
    return store


def _make_product(
    store: Store,
    *,
    name: str = "Product",
    price: int = 100,
    stock: int = 20,
    prepayment_type: str = Product.PrepaymentType.NONE,
) -> Product:
    with tenant_scope_from_store(store=store, reason="test fixture"):
        category = Category.objects.create(store=store, name=f"{name} Category", slug="")
        product = Product.objects.create(
            store=store,
            category=category,
            name=name,
            price=price,
            stock=stock,
            status=Product.Status.ACTIVE,
            is_active=True,
            prepayment_type=prepayment_type,
        )
        Inventory.objects.get_or_create(
            product=product,
            variant=None,
            defaults={"quantity": max(0, int(stock))},
        )
    return product


def _make_zone(store: Store) -> ShippingZone:
    return ShippingZone.objects.create(store=store, name="Main Zone", is_active=True)


def _api_key_client(api_key: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key}")
    return client


def _admin_client_for_store(store: Store) -> APIClient:
    _ensure_default_plan()
    user = User.objects.create_user(
        email=f"admin-{store.public_id}@example.com",
        password="pass1234",
        is_verified=True,
    )
    StoreMembership.objects.create(
        user=user,
        store=store,
        role=StoreMembership.Role.ADMIN,
        is_active=True,
    )
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": "pass1234"},
        format="json",
    )
    assert resp.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
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


# ---------- Cart prepayment resolver ---------------------------------------

def test_resolve_cart_prepayment_strongest_wins():
    class _P:
        def __init__(self, t):
            self.prepayment_type = t

    assert resolve_cart_prepayment_type([]) == "none"
    assert resolve_cart_prepayment_type([_P("none"), _P("none")]) == "none"
    assert (
        resolve_cart_prepayment_type([_P("none"), _P("delivery_only")])
        == "delivery_only"
    )
    assert (
        resolve_cart_prepayment_type([_P("delivery_only"), _P("full")]) == "full"
    )
    assert (
        resolve_cart_prepayment_type([_P("full"), _P("none"), _P("delivery_only")])
        == "full"
    )


# ---------- Order creation flow --------------------------------------------

@pytest.mark.django_db
def test_order_create_none_is_pending():
    store = _make_store("Prepay None")
    product = _make_product(store, name="Regular")
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)

    resp = client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    )
    assert resp.status_code == 201
    assert resp.data["status"] == Order.Status.PENDING
    assert resp.data["payment_status"] == Order.PaymentStatus.NONE
    assert resp.data["prepayment_type"] == "none"
    assert resp.data["requires_payment"] is False


@pytest.mark.django_db
def test_order_create_full_prepayment_is_payment_pending():
    store = _make_store("Prepay Full")
    product = _make_product(
        store, name="Expensive", prepayment_type=Product.PrepaymentType.FULL
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)

    resp = client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    )
    assert resp.status_code == 201
    assert resp.data["status"] == Order.Status.PAYMENT_PENDING
    assert resp.data["payment_status"] == Order.PaymentStatus.NONE
    assert resp.data["prepayment_type"] == "full"
    assert resp.data["requires_payment"] is True


# ---------- Payment submission ---------------------------------------------

@pytest.mark.django_db
def test_payment_submit_happy_path():
    store = _make_store("Submit Happy")
    product = _make_product(
        store, name="Item", prepayment_type=Product.PrepaymentType.DELIVERY_ONLY
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)

    create_resp = client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    )
    assert create_resp.status_code == 201
    public_id = create_resp.data["public_id"]

    pay_resp = client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "TRX-1", "payer_number": "01700000001"},
        format="json",
    )
    assert pay_resp.status_code == 200
    assert pay_resp.data["status"] == Order.Status.PAYMENT_PENDING
    assert pay_resp.data["payment_status"] == Order.PaymentStatus.SUBMITTED
    assert pay_resp.data["transaction_id"] == "TRX-1"
    assert pay_resp.data["payer_number"] == "01700000001"


@pytest.mark.django_db
def test_payment_submit_rejects_blank_fields():
    store = _make_store("Submit Blank")
    product = _make_product(
        store, name="Item", prepayment_type=Product.PrepaymentType.FULL
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)
    public_id = client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]

    r = client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "", "payer_number": ""},
        format="json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_payment_submit_rejects_non_prepayment_order():
    store = _make_store("Submit None")
    product = _make_product(store, name="Regular")
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)
    public_id = client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]

    r = client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "T", "payer_number": "01700000001"},
        format="json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_payment_submit_cannot_double_submit():
    store = _make_store("Submit Double")
    product = _make_product(
        store, name="Item", prepayment_type=Product.PrepaymentType.FULL
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    client = _api_key_client(key)
    public_id = client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]

    ok = client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "T1", "payer_number": "01700000001"},
        format="json",
    )
    assert ok.status_code == 200

    second = client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "T2", "payer_number": "01700000002"},
        format="json",
    )
    assert second.status_code == 400


@pytest.mark.django_db
def test_payment_submit_is_tenant_scoped():
    store_a = _make_store("Tenant A")
    store_b = _make_store("Tenant B")
    product_b = _make_product(
        store_b, name="ItemB", prepayment_type=Product.PrepaymentType.FULL
    )
    zone_b = _make_zone(store_b)
    _row_a, key_a = create_store_api_key(store_a, name="frontend-a")
    _row_b, key_b = create_store_api_key(store_b, name="frontend-b")

    client_b = _api_key_client(key_b)
    client_a = _api_key_client(key_a)

    order_b_public = client_b.post(
        "/api/v1/orders/", _checkout_payload(product_b, zone_b), format="json"
    ).data["public_id"]

    cross = client_a.post(
        f"/api/v1/orders/{order_b_public}/payment/",
        {"transaction_id": "X", "payer_number": "01700000001"},
        format="json",
    )
    assert cross.status_code == 404


# ---------- Admin verify-payment -------------------------------------------

@pytest.mark.django_db
def test_admin_verify_payment_valid_confirms_order():
    store = _make_store("Verify OK")
    product = _make_product(
        store,
        name="Item",
        stock=3,
        prepayment_type=Product.PrepaymentType.FULL,
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    sf_client = _api_key_client(key)
    admin_client = _admin_client_for_store(store)

    public_id = sf_client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]
    sf_client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "T", "payer_number": "01700000001"},
        format="json",
    )

    r = admin_client.post(
        f"/api/v1/admin/orders/{public_id}/verify-payment/",
        {"valid": True},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["order"]["status"] == Order.Status.CONFIRMED
    assert r.data["order"]["payment_status"] == Order.PaymentStatus.VERIFIED


@pytest.mark.django_db
def test_admin_verify_payment_invalid_cancels_and_restores_stock():
    store = _make_store("Verify Reject")
    product = _make_product(
        store,
        name="Item",
        stock=3,
        prepayment_type=Product.PrepaymentType.FULL,
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    sf_client = _api_key_client(key)
    admin_client = _admin_client_for_store(store)

    public_id = sf_client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]
    sf_client.post(
        f"/api/v1/orders/{public_id}/payment/",
        {"transaction_id": "T", "payer_number": "01700000001"},
        format="json",
    )

    r = admin_client.post(
        f"/api/v1/admin/orders/{public_id}/verify-payment/",
        {"valid": False},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["order"]["status"] == Order.Status.CANCELLED
    assert r.data["order"]["payment_status"] == Order.PaymentStatus.FAILED

    with tenant_scope_from_store(store=store, reason="test assertions"):
        assert StockRestoreLog.objects.filter(
            order__public_id=public_id
        ).count() == 1


@pytest.mark.django_db
def test_admin_verify_requires_submitted_state():
    store = _make_store("Verify Guard")
    product = _make_product(
        store, name="Item", prepayment_type=Product.PrepaymentType.FULL
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    sf_client = _api_key_client(key)
    admin_client = _admin_client_for_store(store)

    public_id = sf_client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]

    # Submission has NOT happened yet — verification must fail.
    r = admin_client.post(
        f"/api/v1/admin/orders/{public_id}/verify-payment/",
        {"valid": True},
        format="json",
    )
    assert r.status_code == 400


# ---------- Admin status change guard --------------------------------------

@pytest.mark.django_db
def test_status_change_blocks_payment_pending_to_confirmed_without_verification():
    store = _make_store("Status Guard")
    product = _make_product(
        store, name="Item", prepayment_type=Product.PrepaymentType.FULL
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    sf_client = _api_key_client(key)
    public_id = sf_client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]

    with tenant_scope_from_store(store=store, reason="test assertions"):
        order = Order.objects.get(public_id=public_id)
        assert order.status == Order.Status.PAYMENT_PENDING
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError):
            apply_order_status_change(order=order, to_status=Order.Status.CONFIRMED)


@pytest.mark.django_db
def test_service_submit_and_verify_round_trip():
    """Pure-service round trip bypassing HTTP layer, exercising helpers directly."""
    store = _make_store("Service Round Trip")
    product = _make_product(
        store,
        name="Item",
        stock=2,
        prepayment_type=Product.PrepaymentType.DELIVERY_ONLY,
    )
    zone = _make_zone(store)
    _row, key = create_store_api_key(store, name="frontend")
    sf_client = _api_key_client(key)
    public_id = sf_client.post(
        "/api/v1/orders/", _checkout_payload(product, zone), format="json"
    ).data["public_id"]

    with tenant_scope_from_store(store=store, reason="test assertions"):
        order = Order.objects.get(public_id=public_id)
        submit_order_payment(
            order=order,
            transaction_id="T-round",
            payer_number="01711111111",
        )
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.SUBMITTED
        apply_payment_verification(order=order, valid=True)
        order.refresh_from_db()
        assert order.status == Order.Status.CONFIRMED
        assert order.payment_status == Order.PaymentStatus.VERIFIED
