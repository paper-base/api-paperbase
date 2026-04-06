"""Immutable purchase ledger and adjustments."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from engine.apps.customers.models import Customer
from engine.apps.orders.models import (
    Order,
    OrderItem,
    PurchaseLedgerAdjustment,
    PurchaseLedgerEntry,
)
from engine.apps.stores.services import create_store_api_key
from engine.core.tenant_execution import tenant_scope_from_store
from engine.core.trash_service import soft_delete_order

from tests.apps.orders.test_order_item_snapshots import (
    _api_key_client,
    _make_product,
    _make_store,
    _make_zone,
)
from tests.core.test_core import _ensure_default_plan, _make_membership, make_user

User = get_user_model()


@pytest.mark.django_db
def test_storefront_order_creates_ledger_entries():
    store = _make_store("Ledger Storefront")
    product = _make_product(store, name="Ledger Tee", price=199, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    payload = {
        "shipping_zone_public_id": zone.public_id,
        "shipping_name": "Bob",
        "phone": "01712345678",
        "email": "bob@example.com",
        "shipping_address": "Dhaka",
        "products": [{"product_public_id": product.public_id, "quantity": 2}],
    }
    response = client.post("/api/v1/orders/", payload, format="json")
    assert response.status_code == 201
    opid = response.data["public_id"]

    with tenant_scope_from_store(store=store, reason="test assertions"):
        item = OrderItem.objects.select_related("order", "product").get(order__public_id=opid)
        entries = list(PurchaseLedgerEntry.objects.filter(order_public_id=opid))
        assert len(entries) == 1
        e = entries[0]
        assert e.order_item_public_id == item.public_id
        assert e.product_public_id == product.public_id
        assert e.product_name == "Ledger Tee"
        assert e.quantity == 2
        assert e.unit_price == Decimal("199.00")
        assert e.order_status_snapshot == Order.Status.PENDING
        assert e.customer_id == item.order.customer_id


@pytest.mark.django_db
def test_ledger_survives_order_soft_delete():
    store = _make_store("Ledger Delete")
    product = _make_product(store, name="Keep Name", price=50, stock=5)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    payload = {
        "shipping_zone_public_id": zone.public_id,
        "shipping_name": "Carol",
        "phone": "01787654321",
        "email": "carol@example.com",
        "shipping_address": "Dhaka",
        "products": [{"product_public_id": product.public_id, "quantity": 1}],
    }
    response = client.post("/api/v1/orders/", payload, format="json")
    assert response.status_code == 201
    opid = response.data["public_id"]

    with tenant_scope_from_store(store=store, reason="test assertions"):
        order = Order.objects.get(public_id=opid)
        item = OrderItem.objects.get(order=order)
        oit_pid = item.public_id
        assert PurchaseLedgerEntry.objects.filter(order_public_id=opid).count() == 1

    deleter = make_user("deleter@example.com")
    _make_membership(deleter, store)
    with tenant_scope_from_store(store=store, reason="soft delete order"):
        order = Order.objects.get(public_id=opid)
        soft_delete_order(order=order, store=store, deleted_by=deleter)

    with tenant_scope_from_store(store=store, reason="test assertions"):
        assert not Order.objects.filter(public_id=opid).exists()
        e = PurchaseLedgerEntry.objects.get(order_item_public_id=oit_pid)
        assert e.order_id is None
        assert e.order_item_id is None
        assert e.order_public_id == opid
        assert e.product_name == "Keep Name"

    _ensure_default_plan()
    admin = make_user("ledger-delete-details@example.com", is_staff=True)
    _make_membership(admin, store)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)
    admin_client.credentials(HTTP_X_STORE_PUBLIC_ID=store.public_id)
    customer = Customer.objects.get(store=store, phone="01787654321")
    detail_resp = admin_client.get(f"/api/v1/admin/customers/{customer.public_id}/details/")
    assert detail_resp.status_code == 200
    assert detail_resp.data["analytics"]["total_orders"] == 1
    assert Decimal(str(detail_resp.data["analytics"]["total_spent"])) == Decimal("50.00")
    assert len(detail_resp.data["ordered_products"]) == 1


@pytest.mark.django_db
def test_admin_patch_quantity_creates_adjustment():
    _ensure_default_plan()
    store = _make_store("Ledger Adjust")
    product = _make_product(store, name="Adj Product", price=100, stock=20)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    payload = {
        "shipping_zone_public_id": zone.public_id,
        "shipping_name": "Dan",
        "phone": "01711112222",
        "email": "dan@example.com",
        "shipping_address": "Dhaka",
        "products": [{"product_public_id": product.public_id, "quantity": 2}],
    }
    response = client.post("/api/v1/orders/", payload, format="json")
    assert response.status_code == 201
    opid = response.data["public_id"]

    with tenant_scope_from_store(store=store, reason="test assertions"):
        item = OrderItem.objects.get(order__public_id=opid)
        oit_pid = item.public_id
        assert item.quantity == 2

    admin = make_user("ledger-admin@example.com", is_staff=True)
    _make_membership(admin, store)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)
    admin_client.credentials(HTTP_X_STORE_PUBLIC_ID=store.public_id)

    patch_resp = admin_client.patch(
        f"/api/v1/admin/orders/{opid}/",
        {"items": [{"public_id": oit_pid, "quantity": 5}]},
        format="json",
    )
    assert patch_resp.status_code == 200, patch_resp.data

    with tenant_scope_from_store(store=store, reason="test assertions"):
        adj = PurchaseLedgerAdjustment.objects.filter(
            order_item_public_id=oit_pid,
            field_key=PurchaseLedgerAdjustment.FieldKey.QUANTITY,
        ).first()
        assert adj is not None
        assert adj.old_value == 2
        assert adj.new_value == 5
        entry = PurchaseLedgerEntry.objects.get(order_item_public_id=oit_pid)
        assert entry.quantity == 2

    detail_resp = admin_client.get(
        f"/api/v1/admin/customers/{Customer.objects.get(store=store, phone='01711112222').public_id}/details/",
    )
    assert detail_resp.status_code == 200
    assert detail_resp.data["analytics"]["total_orders"] == 1
    assert Decimal(str(detail_resp.data["analytics"]["total_spent"])) == Decimal("200.00")


@pytest.mark.django_db
def test_customer_list_exposes_ledger_order_count():
    _ensure_default_plan()
    store = _make_store("Ledger List Count")
    product = _make_product(store, name="List Product", price=40, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    response = client.post(
        "/api/v1/orders/",
        {
            "shipping_zone_public_id": zone.public_id,
            "shipping_name": "Listy",
            "phone": "01755556666",
            "email": "listy@example.com",
            "shipping_address": "Dhaka",
            "products": [{"product_public_id": product.public_id, "quantity": 1}],
        },
        format="json",
    )
    assert response.status_code == 201
    customer = Customer.objects.get(store=store, phone="01755556666")
    admin = make_user("ledger-list@example.com", is_staff=True)
    _make_membership(admin, store)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)
    admin_client.credentials(HTTP_X_STORE_PUBLIC_ID=store.public_id)
    list_resp = admin_client.get("/api/v1/admin/customers/")
    assert list_resp.status_code == 200
    results = list_resp.data.get("results", list_resp.data)
    row = next(r for r in results if r["public_id"] == customer.public_id)
    assert row["ledger_order_count"] == 1
    assert Decimal(str(row["ledger_total_spent"])) == Decimal("40.00")
    assert "total_orders" in row


@pytest.mark.django_db
def test_two_orders_ledger_analytics_on_customer_details():
    _ensure_default_plan()
    store = _make_store("Ledger Two Orders")
    product = _make_product(store, name="Two Ord P", price=10, stock=50)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)
    phone = "01777778888"
    for _ in range(2):
        r = client.post(
            "/api/v1/orders/",
            {
                "shipping_zone_public_id": zone.public_id,
                "shipping_name": "Twin",
                "phone": phone,
                "email": "twin@example.com",
                "shipping_address": "Dhaka",
                "products": [{"product_public_id": product.public_id, "quantity": 1}],
            },
            format="json",
        )
        assert r.status_code == 201
    customer = Customer.objects.get(store=store, phone=phone)
    admin = make_user("ledger-two@example.com", is_staff=True)
    _make_membership(admin, store)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)
    admin_client.credentials(HTTP_X_STORE_PUBLIC_ID=store.public_id)
    detail_resp = admin_client.get(f"/api/v1/admin/customers/{customer.public_id}/details/")
    assert detail_resp.status_code == 200
    assert detail_resp.data["analytics"]["total_orders"] == 2
    assert Decimal(str(detail_resp.data["analytics"]["total_spent"])) == Decimal("20.00")
    assert Decimal(str(detail_resp.data["analytics"]["average_order_value"])) == Decimal("10.00")


@pytest.mark.django_db
def test_customer_details_shows_ledger_product_name_not_live_catalog():
    _ensure_default_plan()
    store = _make_store("Ledger Customer Details")
    product = _make_product(store, name="Original Name", price=80, stock=10)
    zone = _make_zone(store)
    _key_row, api_key = create_store_api_key(store, name="frontend")
    client = _api_key_client(api_key)

    payload = {
        "shipping_zone_public_id": zone.public_id,
        "shipping_name": "Eve",
        "phone": "01733334444",
        "email": "eve@example.com",
        "shipping_address": "Dhaka",
        "products": [{"product_public_id": product.public_id, "quantity": 1}],
    }
    response = client.post("/api/v1/orders/", payload, format="json")
    assert response.status_code == 201

    with tenant_scope_from_store(store=store, reason="rename product"):
        product.name = "Renamed In Catalog"
        product.save(update_fields=["name"])
        customer = Customer.objects.get(store=store, phone="01733334444")

    admin = make_user("cust-details-admin@example.com", is_staff=True)
    _make_membership(admin, store)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)
    admin_client.credentials(HTTP_X_STORE_PUBLIC_ID=store.public_id)

    detail_resp = admin_client.get(
        f"/api/v1/admin/customers/{customer.public_id}/details/",
    )
    assert detail_resp.status_code == 200
    rows = detail_resp.data["ordered_products"]
    assert len(rows) == 1
    assert rows[0]["product_name"] == "Original Name"
    assert rows[0]["order_status_at_purchase"] == Order.Status.PENDING
