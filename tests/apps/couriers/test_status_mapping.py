from django.test import SimpleTestCase

from engine.apps.couriers.models import Courier
from engine.apps.couriers.status_mapping import courier_status_implies_order_confirmed


class CourierStatusMappingTests(SimpleTestCase):
    def test_pathao_picked_up(self):
        self.assertTrue(
            courier_status_implies_order_confirmed(Courier.Provider.PATHAO, "picked_up")
        )

    def test_steadfast_in_transit(self):
        self.assertTrue(
            courier_status_implies_order_confirmed(Courier.Provider.STEADFAST, "in_transit")
        )

    def test_pending_not_confirmed(self):
        self.assertFalse(
            courier_status_implies_order_confirmed(Courier.Provider.PATHAO, "pending")
        )
