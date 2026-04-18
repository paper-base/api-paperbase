"""Canonical purchase service: get_confirmed_orders, get_customer_purchase_metrics."""

import logging
from decimal import Decimal

import pytest
from engine.apps.customers.models import Customer
from engine.apps.customers.services.purchase_service import (
    get_confirmed_orders,
    get_confirmed_orders_for_store,
    get_customer_purchase_metrics,
)
from engine.apps.customers.services.consistency_check import (
    validate_customer_purchase_consistency,
)
from engine.apps.orders.models import Order
from engine.apps.orders.services import apply_order_status_change
from tests.core.test_core import _make_order
from tests.apps.orders.test_order_item_snapshots import _make_store


@pytest.mark.django_db
def test_get_confirmed_orders_scoped_to_customer_and_status():
    store = _make_store("Confirmed Qs")
    a = Customer.objects.create(store=store, phone="01700000001", name="A")
    b = Customer.objects.create(store=store, phone="01700000002", name="B")
    oa = _make_order(store, email="a@example.com", phone=a.phone)
    oa.customer = a
    oa.subtotal_after_discount = Decimal("10.00")
    oa.save(update_fields=["customer", "subtotal_after_discount"])
    ob = _make_order(store, email="b@example.com", phone=b.phone)
    ob.customer = b
    ob.subtotal_after_discount = Decimal("20.00")
    ob.save(update_fields=["customer", "subtotal_after_discount"])
    apply_order_status_change(order=oa, to_status=Order.Status.CONFIRMED)

    assert list(get_confirmed_orders(a).values_list("id", flat=True)) == [oa.id]
    assert get_confirmed_orders(b).count() == 0
    assert get_confirmed_orders(None).count() == 0


@pytest.mark.django_db
def test_get_confirmed_orders_excludes_non_confirmed():
    store = _make_store("Confirmed Qs2")
    c = Customer.objects.create(store=store, phone="01700000003", name="C")
    o = _make_order(store, email="c@example.com", phone=c.phone)
    o.customer = c
    o.subtotal_after_discount = Decimal("5.00")
    o.save(update_fields=["customer", "subtotal_after_discount"])
    assert get_confirmed_orders(c).count() == 0
    apply_order_status_change(order=o, to_status=Order.Status.CONFIRMED)
    assert get_confirmed_orders(c).count() == 1
    assert get_confirmed_orders(c).get().status == Order.Status.CONFIRMED


@pytest.mark.django_db
def test_get_confirmed_orders_for_store():
    store = _make_store("Store confirmed qs")
    c1 = Customer.objects.create(store=store, phone="01700000020", name="C1")
    c2 = Customer.objects.create(store=store, phone="01700000021", name="C2")
    o1 = _make_order(store, email="s@example.com", phone=c1.phone)
    o1.customer = c1
    o1.subtotal_after_discount = Decimal("1.00")
    o1.save(update_fields=["customer", "subtotal_after_discount"])
    o2 = _make_order(store, email="t@example.com", phone=c2.phone)
    o2.customer = c2
    o2.subtotal_after_discount = Decimal("2.00")
    o2.save(update_fields=["customer", "subtotal_after_discount"])
    apply_order_status_change(order=o1, to_status=Order.Status.CONFIRMED)
    assert get_confirmed_orders_for_store(store).count() == 1
    apply_order_status_change(order=o2, to_status=Order.Status.CONFIRMED)
    assert get_confirmed_orders_for_store(store).count() == 2


@pytest.mark.django_db
def test_get_customer_purchase_metrics_matches_confirmed_spend():
    store = _make_store("Purchase metrics")
    c = Customer.objects.create(store=store, phone="01700000004", name="D")
    o = _make_order(store, email="d@example.com", phone=c.phone)
    o.customer = c
    o.subtotal_after_discount = Decimal("15.00")
    o.save(update_fields=["customer", "subtotal_after_discount"])
    apply_order_status_change(order=o, to_status=Order.Status.CONFIRMED)
    metrics = get_customer_purchase_metrics(c)
    assert metrics.total_orders == 1
    assert metrics.total_spent == Decimal("15.00")
    assert metrics.average_order_value == Decimal("15.00")


@pytest.mark.django_db
def test_validate_customer_purchase_consistency_warns_on_drift(caplog):
    caplog.set_level(logging.WARNING, logger="engine.apps.customers.services.consistency_check")
    store = _make_store("Consistency")
    c = Customer.objects.create(store=store, phone="01700000011", name="E")
    o = _make_order(store, email="e@example.com", phone=c.phone)
    o.customer = c
    o.subtotal_after_discount = Decimal("99.00")
    o.save(update_fields=["customer", "subtotal_after_discount"])
    apply_order_status_change(order=o, to_status=Order.Status.CONFIRMED)
    c.total_spent = Decimal("0.00")
    c.save(update_fields=["total_spent", "updated_at"])
    assert validate_customer_purchase_consistency(c) is False
    assert "mismatch" in caplog.text.lower() or "total_spent" in caplog.text
