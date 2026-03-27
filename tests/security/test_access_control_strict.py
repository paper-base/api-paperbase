import hashlib
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import path
from rest_framework.test import APIClient
from rest_framework.views import APIView

from engine.apps.orders.models import Order, OrderItem
from engine.apps.products.models import Category, Product
from engine.apps.reviews.models import Review
from engine.apps.reviews import services as review_services
from engine.apps.shipping.models import ShippingZone
from engine.apps.stores.models import Store, StoreMembership, StoreSession
from engine.apps.stores.services import create_store_api_key, revoke_store_api_key
from engine.core.store_session import derive_store_session_id, validate_store_session_consistency
from engine.core import store_api_key_auth
from engine.core.apps import enforce_production_override_safety
from engine.core.store_api_key_auth import (
    STORE_FRONTEND_ROUTE_POLICY,
    validate_storefront_api_key_view_flags,
    maybe_validate_storefront_api_key_view_flags,
)
from config.permissions import IsStorefrontAPIKey

User = get_user_model()


@pytest.fixture(autouse=True)
def _enable_tenant_api_key_enforcement(settings):
    settings.TENANT_API_KEY_ENFORCE = True


def _make_store(name: str) -> Store:
    return Store.objects.create(
        name=name,
        owner_name=f"{name} Owner",
        owner_email=f"{name.lower().replace(' ', '')}@example.com",
    )


def _make_product(store: Store, *, name: str = "Product", price: int = 100, stock: int = 20) -> Product:
    category = Category.objects.create(
        store=store,
        name=f"{name} Category",
        slug=f"{name.lower().replace(' ', '-')}-cat",
    )
    return Product.objects.create(
        store=store,
        category=category,
        name=name,
        price=price,
        stock=stock,
        status=Product.Status.ACTIVE,
        is_active=True,
    )


def _make_zone(store: Store) -> ShippingZone:
    return ShippingZone.objects.create(store=store, name="Main Zone", is_active=True)


def _api_key_client(api_key: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key}")
    return client


def _session_headers(token: str) -> dict:
    return {"HTTP_X_STORE_SESSION_TOKEN": token}


def _admin_client_for_store(store: Store) -> APIClient:
    user = User.objects.create_user(
        email=f"admin-{store.public_id}@example.com",
        password="pass1234",
    )
    user.is_verified = True
    user.is_staff = True
    user.save(update_fields=["is_verified", "is_staff"])
    StoreMembership.objects.create(
        user=user,
        store=store,
        role=StoreMembership.Role.OWNER,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_STORE_PUBLIC_ID=store.public_id)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/v1/products/", "/api/v1/categories/"])
def test_storefront_api_key_allows_catalog_reads(path):
    store = _make_store("Catalog")
    _make_product(store, name="Visible Product")
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    response = client.get(path)

    assert response.status_code == 200


@pytest.mark.django_db
def test_api_key_can_create_order_valid_payload():
    store = _make_store("Orders")
    product = _make_product(store, price=150, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 2}],
    }
    response = client.post("/api/v1/orders/direct/", payload, format="json")

    assert response.status_code == 201
    order = Order.objects.get(public_id=response.data["public_id"])
    assert order.store_id == store.id
    assert str(order.subtotal) == "300.00"
    assert order.store_session_id.startswith("ssn_")
    assert response.headers.get("X-Store-Session-Id") == order.store_session_id
    assert response.headers.get("X-Store-Session-Token")


@pytest.mark.django_db
def test_api_key_order_with_fake_price_field_fails():
    store = _make_store("Orders")
    product = _make_product(store, price=150, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 2, "price": "1.00"}],
    }
    response = client.post("/api/v1/orders/direct/", payload, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_api_key_order_with_other_store_product_fails():
    store_a = _make_store("Store A")
    store_b = _make_store("Store B")
    product_b = _make_product(store_b, price=200, stock=5)
    zone_a = _make_zone(store_a)
    _key_row, api_key_a = create_store_api_key(store_a, name="frontend-a")
    client = _api_key_client(api_key_a)

    payload = {
        "shipping_zone": zone_a.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product_b.public_id, "quantity": 1}],
    }
    response = client.post("/api/v1/orders/direct/", payload, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/orders/"),
        ("get", "/api/v1/orders/non-existent/"),
        ("patch", "/api/v1/orders/non-existent/"),
        ("get", "/api/v1/customers/me/"),
        ("get", "/api/v1/admin/analytics/overview/"),
    ],
)
def test_api_key_restricted_access_is_blocked(method, path):
    store = _make_store("Restricted")
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    response = getattr(client, method)(path, {}, format="json")

    assert response.status_code in {401, 403, 404, 405}


@pytest.mark.django_db
def test_auth_missing_invalid_and_revoked_api_key():
    store = _make_store("Auth")
    _make_product(store, name="Auth Product")
    key_row, valid_key = create_store_api_key(store, name="frontend")

    client = APIClient()
    missing = client.get("/api/v1/products/")
    assert missing.status_code == 401

    invalid = client.get("/api/v1/products/", HTTP_AUTHORIZATION="Bearer ak_live_invalid")
    assert invalid.status_code == 401

    revoke_store_api_key(key_row)
    revoked = client.get("/api/v1/products/", HTTP_AUTHORIZATION=f"Bearer {valid_key}")
    assert revoked.status_code == 401


@pytest.mark.django_db
def test_cross_tenant_order_access_fails_with_api_key():
    store_a = _make_store("Store A")
    store_b = _make_store("Store B")
    zone_b = _make_zone(store_b)
    order_b = Order.objects.create(
        store=store_b,
        order_number="SECURE0001",
        email="b@example.com",
        shipping_name="Bob",
        shipping_address="Addr",
        phone="01700000000",
        shipping_zone=zone_b,
    )
    _key_row, api_key_a = create_store_api_key(store_a, name="frontend-a")
    client = _api_key_client(api_key_a)

    response = client.get(f"/api/v1/orders/{order_b.public_id}/", {"email": "b@example.com"})

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_api_key_orders_my_returns_session_scoped_orders_only():
    store = _make_store("My Orders")
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    session_token = "session-token-own-orders"
    store_session_id = derive_store_session_id(store_id=store.id, token=session_token)

    own = Order.objects.create(
        store=store,
        order_number="OWN0001",
        email="guest@example.com",
        store_session_id=store_session_id,
        shipping_name="Guest",
        shipping_address="Addr",
        phone="01700000000",
        shipping_zone=zone,
    )
    Order.objects.create(
        store=store,
        order_number="OTHER0001",
        email="other@example.com",
        store_session_id=derive_store_session_id(store_id=store.id, token="other-session"),
        shipping_name="Other",
        shipping_address="Addr",
        phone="01711111111",
        shipping_zone=zone,
    )

    response = client.get("/api/v1/orders/my/", **_session_headers(session_token))
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["public_id"] == own.public_id
    assert response.data["session_initialized"] is True
    assert response.data["requires_session_init"] is False
    assert response.data["session_status"] == "active"


@pytest.mark.django_db
def test_api_key_orders_my_missing_session_context_returns_empty_contract():
    store = _make_store("My Orders Empty")
    _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    other_client = _api_key_client(api_key)
    response = other_client.get("/api/v1/orders/my/")
    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["session_initialized"] is False
    assert response.data["requires_session_init"] is True
    assert response.data["session_status"] == "missing"


@pytest.mark.django_db
def test_api_key_reused_across_sessions_keeps_orders_isolated():
    store = _make_store("Session Isolation")
    product = _make_product(store, price=150, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    base_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }

    create_a = client.post(
        "/api/v1/orders/direct/",
        base_payload,
        format="json",
        **_session_headers("session-A"),
    )
    assert create_a.status_code == 201
    create_b = client.post(
        "/api/v1/orders/direct/",
        base_payload,
        format="json",
        **_session_headers("session-B"),
    )
    assert create_b.status_code == 201

    list_a = client.get("/api/v1/orders/my/", **_session_headers("session-A"))
    list_b = client.get("/api/v1/orders/my/", **_session_headers("session-B"))
    assert list_a.status_code == 200
    assert list_b.status_code == 200
    a_ids = {row["public_id"] for row in list_a.data["results"]}
    b_ids = {row["public_id"] for row in list_b.data["results"]}
    assert create_a.data["public_id"] in a_ids
    assert create_b.data["public_id"] not in a_ids
    assert create_b.data["public_id"] in b_ids
    assert create_a.data["public_id"] not in b_ids


@pytest.mark.django_db
def test_store_session_id_is_deterministic_for_same_store_and_token():
    store = _make_store("Deterministic Session")
    token = "deterministic-token"
    first = derive_store_session_id(store_id=store.id, token=token)
    second = derive_store_session_id(store_id=store.id, token=token)
    assert first == second
    assert validate_store_session_consistency(
        store=store,
        token=token,
        store_session_id=first,
    )


@pytest.mark.django_db
def test_store_session_id_differs_for_same_token_across_stores():
    store_a = _make_store("Store A Session")
    store_b = _make_store("Store B Session")
    token = "shared-token"
    session_a = derive_store_session_id(store_id=store_a.id, token=token)
    session_b = derive_store_session_id(store_id=store_b.id, token=token)
    assert session_a != session_b


def test_api_key_view_scan_raises_when_allow_flag_missing():
    class MissingAllowView(APIView):
        permission_classes = [IsStorefrontAPIKey]
        authentication_classes = []

    patterns = [path("broken/", MissingAllowView.as_view())]
    with pytest.raises(RuntimeError):
        validate_storefront_api_key_view_flags(patterns=patterns)


def test_maybe_validate_scan_warns_only_in_debug(monkeypatch, settings, caplog):
    settings.DEBUG = True
    settings.TESTING = False
    store_api_key_auth._API_KEY_VIEW_SCAN_DONE = False

    def _raise():
        raise RuntimeError("missing allow flag")

    monkeypatch.setattr(store_api_key_auth, "validate_storefront_api_key_view_flags", _raise)
    maybe_validate_storefront_api_key_view_flags()
    assert "missing allow flag" in caplog.text


def test_maybe_validate_scan_raises_in_test_mode(monkeypatch, settings):
    settings.DEBUG = False
    settings.TESTING = True
    store_api_key_auth._API_KEY_VIEW_SCAN_DONE = False

    def _raise():
        raise RuntimeError("missing allow flag")

    monkeypatch.setattr(store_api_key_auth, "validate_storefront_api_key_view_flags", _raise)
    with pytest.raises(RuntimeError):
        maybe_validate_storefront_api_key_view_flags()


def test_maybe_validate_scan_disabled_in_prod(monkeypatch, settings):
    settings.DEBUG = False
    settings.TESTING = False
    store_api_key_auth._API_KEY_VIEW_SCAN_DONE = False
    called = {"value": False}

    def _raise():
        called["value"] = True
        raise RuntimeError("should not be called")

    monkeypatch.setattr(store_api_key_auth, "validate_storefront_api_key_view_flags", _raise)
    maybe_validate_storefront_api_key_view_flags()
    assert called["value"] is False


@pytest.mark.django_db
def test_store_session_metadata_drift_does_not_override_identity():
    store = _make_store("Session Drift")
    product = _make_product(store, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    token = "drift-token"
    derived_id = derive_store_session_id(store_id=store.id, token=token)
    StoreSession.objects.create(
        store=store,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        store_session_id="ssn_drifted_value",
    )
    create_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    response = client.post("/api/v1/orders/direct/", create_payload, format="json", **_session_headers(token))
    assert response.status_code == 201
    order = Order.objects.get(public_id=response.data["public_id"])
    assert order.store_session_id == derived_id
    session_row = StoreSession.objects.get(store=store)
    assert session_row.store_session_id == "ssn_drifted_value"


@pytest.mark.django_db
def test_admin_can_list_orders_with_jwt():
    store = _make_store("Admin Orders")
    zone = _make_zone(store)
    Order.objects.create(
        store=store,
        order_number="ADM0001",
        email="buyer@example.com",
        shipping_name="Buyer",
        shipping_address="Addr",
        phone="01700000000",
        shipping_zone=zone,
    )
    client = _admin_client_for_store(store)
    response = client.get("/api/v1/orders/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_order_payload_edge_cases_fail_safely():
    store = _make_store("Edge")
    product = _make_product(store, stock=50)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    base_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Edge User",
        "phone": "01712345678",
        "email": "edge@example.com",
        "shipping_address": "Address",
    }

    negative_qty = {**base_payload, "products": [{"public_id": product.public_id, "quantity": -1}]}
    assert client.post("/api/v1/orders/direct/", negative_qty, format="json").status_code == 400

    huge_qty = {**base_payload, "products": [{"public_id": product.public_id, "quantity": 999999}]}
    assert client.post("/api/v1/orders/direct/", huge_qty, format="json").status_code == 400

    sql_like_qty = {**base_payload, "products": [{"public_id": product.public_id, "quantity": "1 OR 1=1"}]}
    assert client.post("/api/v1/orders/direct/", sql_like_qty, format="json").status_code == 400

    hidden_fields = {
        **base_payload,
        "products": [{"public_id": product.public_id, "quantity": 1}],
        "total": "0.01",
        "discount": "999",
    }
    assert client.post("/api/v1/orders/direct/", hidden_fields, format="json").status_code == 400

    missing_required = {"products": [{"public_id": product.public_id, "quantity": 1}]}
    assert client.post("/api/v1/orders/direct/", missing_required, format="json").status_code == 400


@pytest.mark.django_db
def test_api_key_can_create_review_valid_payload():
    store = _make_store("Review Store")
    product = _make_product(store, stock=50)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    session_token = "review-session-1"
    create_order_payload = {
        "shipping_zone": _make_zone(store).public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    order_response = client.post(
        "/api/v1/orders/direct/",
        create_order_payload,
        format="json",
        **_session_headers(session_token),
    )
    assert order_response.status_code == 201

    payload = {
        "product": product.public_id,
        "order_public_id": order_response.data["public_id"],
        "rating": 5,
        "title": "Great",
        "body": "This product works very well.",
    }
    response = client.post(
        "/api/v1/reviews/create/",
        payload,
        format="json",
        **_session_headers(session_token),
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_api_key_review_invalid_payload_fails():
    store = _make_store("Review Invalid")
    product = _make_product(store, stock=50)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    short_body = {
        "product": product.public_id,
        "order_public_id": "ord_invalid",
        "rating": 4,
        "title": "Bad",
        "body": "ok",
    }
    assert client.post("/api/v1/reviews/create/", short_body, format="json").status_code == 400

    missing_product = {
        "order_public_id": "ord_invalid",
        "rating": 4,
        "title": "Bad",
        "body": "Valid length body",
    }
    assert client.post("/api/v1/reviews/create/", missing_product, format="json").status_code == 400


@pytest.mark.django_db
def test_api_key_review_duplicate_by_guest_is_blocked():
    store = _make_store("Review Duplicate")
    product = _make_product(store, stock=50)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    session_token = "review-session-dup"
    create_order_payload = {
        "shipping_zone": _make_zone(store).public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    order_response = client.post(
        "/api/v1/orders/direct/",
        create_order_payload,
        format="json",
        **_session_headers(session_token),
    )
    assert order_response.status_code == 201
    payload = {
        "product": product.public_id,
        "order_public_id": order_response.data["public_id"],
        "rating": 5,
        "title": "Great",
        "body": "Really like this one.",
    }
    first = client.post("/api/v1/reviews/create/", payload, format="json", **_session_headers(session_token))
    assert first.status_code == 201

    second = client.post("/api/v1/reviews/create/", payload, format="json", **_session_headers(session_token))
    assert second.status_code == 400


@pytest.mark.django_db
def test_api_key_review_with_mismatched_session_is_blocked():
    store = _make_store("Review Session Mismatch")
    product = _make_product(store, stock=50)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    order_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    order_response = client.post(
        "/api/v1/orders/direct/",
        order_payload,
        format="json",
        **_session_headers("review-session-match"),
    )
    assert order_response.status_code == 201

    review_payload = {
        "product": product.public_id,
        "order_public_id": order_response.data["public_id"],
        "rating": 5,
        "title": "Mismatch",
        "body": "Should not be accepted due to mismatched session.",
    }
    review_response = client.post(
        "/api/v1/reviews/create/",
        review_payload,
        format="json",
        **_session_headers("different-session-token"),
    )
    assert review_response.status_code == 400


@pytest.mark.django_db
def test_admin_override_allows_legacy_review_binding(settings):
    settings.SECURITY_REVIEW_LEGACY_MODE_ENABLED = True
    settings.SECURITY_INTERNAL_OVERRIDE_ALLOWED = True
    store = _make_store("Review Legacy Override")
    product = _make_product(store, stock=50)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    admin_user = User.objects.create_user(email="staff@example.com", password="pass1234")
    admin_user.is_staff = True
    admin_user.is_verified = True
    admin_user.save(update_fields=["is_staff", "is_verified"])
    client.force_authenticate(user=admin_user)

    order_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    order_response = client.post(
        "/api/v1/orders/direct/",
        order_payload,
        format="json",
        **_session_headers("session-source"),
    )
    assert order_response.status_code == 201

    review_payload = {
        "product": product.public_id,
        "order_public_id": order_response.data["public_id"],
        "allow_legacy_binding": True,
        "rating": 5,
        "title": "Legacy",
        "body": "Support-assisted legacy review.",
    }
    review_response = client.post(
        "/api/v1/reviews/create/",
        review_payload,
        format="json",
        **_session_headers("different-session"),
    )
    assert review_response.status_code == 201


@pytest.mark.django_db
def test_model_validation_rejects_cross_session_even_with_legacy_flag():
    store = _make_store("Persisted Legacy")
    product = _make_product(store, stock=50)
    zone = _make_zone(store)
    order = Order.objects.create(
        store=store,
        order_number="LEGACY0001",
        email="legacy@example.com",
        store_session_id="ssn_original",
        shipping_name="Legacy",
        shipping_address="Addr",
        phone="01700000000",
        shipping_zone=zone,
    )
    OrderItem.objects.create(order=order, product=product, quantity=1, price=product.price)
    with pytest.raises(ValidationError):
        Review.objects.create(
            store=store,
            product=product,
            order=order,
            store_session_id="ssn_mismatched",
            allow_legacy_binding=True,
            rating=5,
            title="Legacy Imported",
            body="Imported legacy review binding.",
            status=Review.Status.PENDING,
        )


@pytest.mark.django_db
def test_orders_my_missing_session_never_leaks_existing_orders():
    store = _make_store("Missing Session Isolation")
    zone = _make_zone(store)
    session_token = "existing-session"
    Order.objects.create(
        store=store,
        order_number="LEAK0001",
        email="leak@example.com",
        store_session_id=derive_store_session_id(store_id=store.id, token=session_token),
        shipping_name="Leak",
        shipping_address="Addr",
        phone="01700000000",
        shipping_zone=zone,
    )
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    response = client.get("/api/v1/orders/my/")
    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["session_status"] == "missing"


@pytest.mark.django_db
def test_internal_override_cannot_be_triggered_by_header_alone(settings):
    settings.SECURITY_REVIEW_LEGACY_MODE_ENABLED = True
    settings.SECURITY_INTERNAL_OVERRIDE_ALLOWED = False
    store = _make_store("Header Bypass Blocked")
    product = _make_product(store, stock=50)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    non_staff = User.objects.create_user(email="user@example.com", password="pass1234")
    non_staff.is_verified = True
    non_staff.save(update_fields=["is_verified"])
    client.force_authenticate(user=non_staff)

    order_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    order_response = client.post(
        "/api/v1/orders/direct/",
        order_payload,
        format="json",
        **_session_headers("session-source"),
    )
    assert order_response.status_code == 201

    review_payload = {
        "product": product.public_id,
        "order_public_id": order_response.data["public_id"],
        "allow_legacy_binding": True,
        "rating": 5,
        "title": "Header attempt",
        "body": "Header alone must not grant bypass.",
    }
    review_response = client.post(
        "/api/v1/reviews/create/",
        review_payload,
        format="json",
        HTTP_X_INTERNAL_REVIEW_BYPASS="1",
        **_session_headers("different-session"),
    )
    assert review_response.status_code == 400


@pytest.mark.django_db
def test_review_override_enforced_by_central_policy(settings, monkeypatch):
    settings.SECURITY_REVIEW_LEGACY_MODE_ENABLED = True
    settings.SECURITY_INTERNAL_OVERRIDE_ALLOWED = True
    store = _make_store("Policy Authority")
    product = _make_product(store, stock=50)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    admin_user = User.objects.create_user(email="policy-staff@example.com", password="pass1234")
    admin_user.is_staff = True
    admin_user.is_verified = True
    admin_user.save(update_fields=["is_staff", "is_verified"])
    client.force_authenticate(user=admin_user)

    order_payload = {
        "shipping_zone": zone.public_id,
        "shipping_name": "Alice",
        "phone": "01712345678",
        "email": "alice@example.com",
        "shipping_address": "Dhaka",
        "products": [{"public_id": product.public_id, "quantity": 1}],
    }
    order_response = client.post(
        "/api/v1/orders/direct/",
        order_payload,
        format="json",
        **_session_headers("session-source"),
    )
    assert order_response.status_code == 201

    monkeypatch.setattr(review_services, "can_override_review", lambda request, action_context: False)
    review_payload = {
        "product": product.public_id,
        "order_public_id": order_response.data["public_id"],
        "allow_legacy_binding": True,
        "rating": 5,
        "title": "Policy denied",
        "body": "Policy must be the only override authority.",
    }
    review_response = client.post(
        "/api/v1/reviews/create/",
        review_payload,
        format="json",
        **_session_headers("different-session"),
    )
    assert review_response.status_code == 400
    assert "allow_legacy_binding" in review_response.data


def test_reviews_app_forbids_direct_is_staff_checks():
    root = Path(__file__).resolve().parents[2]
    reviews_dir = root / "engine" / "apps" / "reviews"
    offenders: list[str] = []
    for path in reviews_dir.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "is_staff" in content:
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"Direct is_staff checks are forbidden in reviews app: {offenders}"


def test_production_safety_gate_blocks_override_flags(settings):
    settings.DEBUG = False
    settings.TESTING = False
    settings.SECURITY_INTERNAL_OVERRIDE_ALLOWED = True
    with pytest.raises(RuntimeError):
        enforce_production_override_safety()


def test_production_safety_gate_blocks_legacy_binding_flag(settings):
    settings.DEBUG = False
    settings.TESTING = False
    settings.SECURITY_INTERNAL_OVERRIDE_ALLOWED = False
    settings.SECURITY_REVIEW_LEGACY_MODE_ENABLED = True
    with pytest.raises(RuntimeError):
        enforce_production_override_safety()


@pytest.mark.django_db
def test_auto_route_policy_with_api_key():
    store = _make_store("Route Policy")
    _make_product(store, name="Policy Product")
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    expected_allowed = {
        ("GET", "/api/v1/products/"),
        ("GET", "/api/v1/categories/"),
        ("GET", "/api/v1/banners/"),
        ("GET", "/api/v1/reviews/"),
        ("GET", "/api/v1/cart/"),
        ("GET", "/api/v1/wishlist/"),
        ("GET", "/api/v1/shipping/options/"),
    }
    for prefix, methods in STORE_FRONTEND_ROUTE_POLICY:
        for method in methods:
            # Skip state-changing routes that need setup payload to avoid false negatives.
            if method == "GET" and prefix not in {"/api/v1/orders/", "/api/v1/orders/my/"}:
                expected_allowed.add((method, prefix))

    checked_routes = sorted(expected_allowed)
    for method, path in checked_routes:
        response = client.generic(method, path)
        assert response.status_code in {200, 201, 204, 400, 404}

    blocked_routes = [
        ("GET", "/api/v1/orders/"),
        ("GET", "/api/v1/orders/non-existent/"),
        ("GET", "/api/v1/admin/orders/"),
        ("GET", "/api/v1/admin/customers/"),
        ("GET", "/api/v1/search/"),
        ("GET", "/api/v1/settings/network/api-keys/"),
    ]
    for method, path in blocked_routes:
        response = client.generic(method, path)
        assert response.status_code in {401, 403, 404}
