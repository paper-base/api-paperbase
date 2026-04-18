"""Unit tests for ``export_csv_format`` (Dhaka time, address, phone)."""

from datetime import datetime, timezone as dt_timezone

from django.test import TestCase

from engine.apps.orders.export_csv_format import (
    convert_to_gmt6,
    format_csv_phone,
    format_full_address,
    format_order_for_csv,
    ORDER_CSV_HEADERS,
)
from engine.apps.orders.models import OrderAddress

from tests.core.test_core import _default_shipping_zone, _make_order, _make_store, make_user


class ConvertToGmt6Tests(TestCase):
    def test_utc_instant_maps_to_dhaka_wall_time(self):
        dt = datetime(2026, 4, 14, 8, 15, 15, 706440, tzinfo=dt_timezone.utc)
        self.assertEqual(convert_to_gmt6(dt), "2026-04-14 14:15:15")

    def test_naive_interpreted_as_utc(self):
        dt = datetime(2026, 1, 1, 0, 0, 0)
        self.assertEqual(convert_to_gmt6(dt), "2026-01-01 06:00:00")

    def test_none_returns_empty(self):
        self.assertEqual(convert_to_gmt6(None), "")


class FormatCsvPhoneTests(TestCase):
    def test_preserves_leading_zero_with_tab_prefix(self):
        self.assertEqual(format_csv_phone("0123456789"), "\t0123456789")

    def test_no_tab_when_no_leading_zero(self):
        self.assertEqual(format_csv_phone("8801711"), "8801711")

    def test_empty(self):
        self.assertEqual(format_csv_phone(""), "")
        self.assertEqual(format_csv_phone(None), "")


class FormatFullAddressTests(TestCase):
    def setUp(self):
        self.user = make_user("csv-fmt-addr@example.com")
        self.store = _make_store("CSV Addr Store", "csv-addr.local", owner_email=self.user.email)
        self.zone = _default_shipping_zone(self.store)

    def test_structured_shipping_address(self):
        order = _make_order(
            self.store,
            shipping_zone=self.zone,
            shipping_address="ignored when structured present",
        )
        OrderAddress.objects.create(
            order=order,
            address_type=OrderAddress.AddressType.SHIPPING,
            name="Ship To",
            phone="",
            address_line1="House 12",
            address_line2="Road 5",
            city="Dhanmondi",
            region="Dhaka",
            postal_code="1209",
            country="Bangladesh",
        )
        order.refresh_from_db()
        # Simulate prefetch cache populated like export task
        list(order.addresses.all())
        self.assertIn("House 12", format_full_address(order))
        self.assertIn("Road 5", format_full_address(order))
        self.assertIn("Dhanmondi", format_full_address(order))
        self.assertIn("Bangladesh", format_full_address(order))

    def test_fallback_shipping_address_and_district(self):
        order = _make_order(
            self.store,
            shipping_zone=self.zone,
            shipping_address="Line A, Line B",
            district="Dhaka",
        )
        self.assertIn("Line A", format_full_address(order))
        self.assertIn("Dhaka", format_full_address(order))


class FormatOrderForCsvTests(TestCase):
    def setUp(self):
        self.user = make_user("csv-fmt-row@example.com")
        self.store = _make_store("CSV Row Store", "csv-row.local", owner_email=self.user.email)
        self.zone = _default_shipping_zone(self.store)

    def test_row_length_matches_headers(self):
        order = _make_order(
            self.store,
            shipping_zone=self.zone,
            phone="0123456789",
        )
        row = format_order_for_csv(order)
        self.assertEqual(len(row), len(ORDER_CSV_HEADERS))
        self.assertEqual(row[ORDER_CSV_HEADERS.index("phone")], "\t0123456789")

    def test_created_at_pattern(self):
        order = _make_order(self.store, shipping_zone=self.zone)
        row = format_order_for_csv(order)
        created = row[ORDER_CSV_HEADERS.index("created_at")]
        self.assertRegex(created, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertNotIn("T", created)
        self.assertNotIn("+", created)
