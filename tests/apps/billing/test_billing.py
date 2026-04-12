"""Billing app tests."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from engine.apps.billing.feature_gate import (
    get_feature_config,
    get_limit,
    has_feature,
    require_feature,
)
from engine.apps.billing.models import Payment, Plan, Subscription
from engine.apps.billing.services import (
    activate_subscription,
    extend_subscription,
    get_active_subscription,
    reject_pending_review_for_payment,
)
from engine.apps.billing.subscription_status import (
    dashboard_subscription_access_ok,
    get_candidate_subscription_row,
    get_subscription_status,
    get_user_subscription_status,
    storefront_blocks_at,
)
from engine.utils.time import BD_TZ, bd_today
from engine.apps.billing.pricing import plan_charge_amount
from engine.apps.stores.models import Store, StoreApiKey, StoreMembership, StoreSettings
from engine.apps.stores.services import allocate_unique_store_code

User = get_user_model()


def _plan_features(limits=None, features=None):
    return {
        "limits": limits or {"max_products": 100},
        "features": features or {"basic_analytics": False, "marketing_tools": False},
    }


class BillingServicesTests(TestCase):
    def setUp(self):
        self.plan_basic = Plan.objects.filter(is_default=True).first()
        if not self.plan_basic:
            self.plan_basic = Plan.objects.create(
                name="basic",
                price=0,
                billing_cycle="monthly",
                features=_plan_features(limits={"max_products": 100}),
                is_default=True,
                is_active=True,
            )
        self.plan_premium = Plan.objects.filter(name="premium").first()
        if not self.plan_premium:
            self.plan_premium = Plan.objects.create(
                name="premium",
                price=999,
                billing_cycle="monthly",
                features=_plan_features(
                    limits={"max_products": 500},
                    features={"basic_analytics": True, "marketing_tools": True},
                ),
                is_active=True,
            )
        self.user = User.objects.create_user(
            username="billinguser",
            email="b@example.com",
            password="pass",
            is_verified=True,
        )

    def test_get_active_subscription_returns_none_when_no_subscription(self):
        self.assertIsNone(get_active_subscription(self.user))

    def test_activate_subscription_creates_subscription_and_payment(self):
        sub = activate_subscription(
            self.user,
            self.plan_basic,
            billing_cycle="monthly",
            duration_days=30,
            source="manual",
            amount=0,
            provider="manual",
        )
        self.assertIsNotNone(sub)
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.plan, self.plan_basic)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.source, Subscription.Source.MANUAL)
        self.assertEqual(sub.payments.count(), 1)
        self.assertEqual(sub.payments.first().status, "success")

    def test_activate_subscription_reuses_pending_payment_no_duplicate_row(self):
        pending = Payment.objects.create(
            user=self.user,
            plan=self.plan_premium,
            subscription=None,
            amount=self.plan_premium.price,
            currency="BDT",
            status=Payment.Status.PENDING,
            provider=Payment.Provider.MANUAL,
            transaction_id="TXN-REUSE-TEST-001",
            metadata={},
        )
        before_count = Payment.objects.filter(user=self.user).count()
        sub = activate_subscription(
            self.user,
            self.plan_premium,
            billing_cycle="monthly",
            duration_days=30,
            source="payment",
            amount=pending.amount,
            provider=pending.provider,
            existing_pending_payment=pending,
        )
        pending.refresh_from_db()
        self.assertEqual(Payment.objects.filter(user=self.user).count(), before_count)
        self.assertEqual(pending.subscription_id, sub.id)
        self.assertEqual(pending.status, Payment.Status.SUCCESS)
        self.assertEqual(pending.transaction_id, "TXN-REUSE-TEST-001")
        self.assertEqual(sub.payments.get().id, pending.id)

    def test_activate_subscription_expires_previous(self):
        activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        activate_subscription(self.user, self.plan_premium, source="manual", amount=999, provider="manual")
        active = get_active_subscription(self.user)
        self.assertIsNotNone(active)
        self.assertEqual(active.plan, self.plan_premium)
        expired = Subscription.objects.filter(user=self.user, status=Subscription.Status.EXPIRED)
        self.assertEqual(expired.count(), 1)

    def test_extend_subscription_adds_days(self):
        sub = activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        original_end = sub.end_date
        extend_subscription(sub, days=14)
        sub.refresh_from_db()
        self.assertEqual((sub.end_date - original_end).days, 14)

    def test_extend_subscription_rejects_canceled(self):
        sub = activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        sub.status = Subscription.Status.CANCELED
        sub.save()
        with self.assertRaises(ValueError):
            extend_subscription(sub, days=14)

    def test_extend_subscription_rejects_expired(self):
        sub = activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        sub.status = Subscription.Status.EXPIRED
        sub.save()
        with self.assertRaises(ValueError):
            extend_subscription(sub, days=14)

    def test_get_subscription_status_grace_and_expired(self):
        sub = activate_subscription(
            self.user, self.plan_basic, source="manual", amount=0, provider="manual"
        )
        end = sub.end_date
        with patch("engine.apps.billing.subscription_status.bd_calendar_date") as m:
            m.return_value = end
            self.assertEqual(get_subscription_status(sub), "ACTIVE")
            m.return_value = end + timedelta(days=1)
            self.assertEqual(get_subscription_status(sub), "GRACE")
            m.return_value = end + timedelta(days=2)
            self.assertEqual(get_subscription_status(sub), "EXPIRED")

    def test_db_expired_status_skips_grace(self):
        sub = activate_subscription(
            self.user, self.plan_basic, source="manual", amount=0, provider="manual"
        )
        sub.status = Subscription.Status.EXPIRED
        sub.save(update_fields=["status"])
        self.assertEqual(get_subscription_status(sub), "EXPIRED")

    def test_pending_review_status_short_circuits_calendar(self):
        today = bd_today()
        sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan_basic,
            status=Subscription.Status.PENDING_REVIEW,
            billing_cycle="monthly",
            start_date=today,
            end_date=today,
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        self.assertEqual(get_subscription_status(sub), "PENDING_REVIEW")
        self.assertEqual(get_user_subscription_status(self.user), "PENDING_REVIEW")
        self.assertTrue(dashboard_subscription_access_ok(self.user))

    def test_rejected_subscription_allows_dashboard_access(self):
        today = bd_today()
        Subscription.objects.create(
            user=self.user,
            plan=self.plan_basic,
            status=Subscription.Status.REJECTED,
            billing_cycle="monthly",
            start_date=today,
            end_date=today,
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        self.assertEqual(get_user_subscription_status(self.user), "REJECTED")
        self.assertTrue(dashboard_subscription_access_ok(self.user))

    def test_none_subscription_allows_dashboard_access(self):
        u = User.objects.create_user(
            username="nonesub",
            email="nonesub@example.com",
            password="pass",
            is_verified=True,
        )
        self.assertEqual(get_user_subscription_status(u), "NONE")
        self.assertTrue(dashboard_subscription_access_ok(u))

    def test_expired_row_precedes_rejected_for_status(self):
        """
        Stale rejection + newer expired paid record: show renew/expired, not payment-rejected.
        (Rejected row must have older updated_at than the expired row.)
        """
        today = bd_today()
        now = timezone.now()
        u = User.objects.create_user(
            username="exprej",
            email="exprej@example.com",
            password="pass",
            is_verified=True,
        )
        expired_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.EXPIRED,
            billing_cycle="monthly",
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=10),
            auto_renew=False,
            source=Subscription.Source.MANUAL,
        )
        rejected_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.REJECTED,
            billing_cycle="monthly",
            start_date=today,
            end_date=today + timedelta(days=30),
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        Subscription.objects.filter(pk=rejected_row.pk).update(
            created_at=now - timedelta(days=200),
            updated_at=now - timedelta(days=200),
        )
        Subscription.objects.filter(pk=expired_row.pk).update(
            updated_at=now - timedelta(days=5),
        )
        cand = get_candidate_subscription_row(u)
        self.assertIsNotNone(cand)
        self.assertEqual(cand.pk, expired_row.pk)
        self.assertEqual(get_user_subscription_status(u), "EXPIRED")

    def test_db_expired_row_precedes_rejected_in_merge(self):
        """Lapsed paid period (DB EXPIRED) must show renew/expired, not a newer REJECTED row."""
        today = bd_today()
        now = timezone.now()
        u = User.objects.create_user(
            username="rejev",
            email="rejev@example.com",
            password="pass",
            is_verified=True,
        )
        expired_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.EXPIRED,
            billing_cycle="monthly",
            start_date=today - timedelta(days=400),
            end_date=today - timedelta(days=300),
            auto_renew=False,
            source=Subscription.Source.MANUAL,
        )
        Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.REJECTED,
            billing_cycle="monthly",
            start_date=today,
            end_date=today + timedelta(days=30),
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        Subscription.objects.filter(pk=expired_row.pk).update(
            created_at=now - timedelta(days=400),
            updated_at=now - timedelta(days=90),
        )
        cand = get_candidate_subscription_row(u)
        self.assertIsNotNone(cand)
        self.assertEqual(cand.pk, expired_row.pk)
        self.assertEqual(get_user_subscription_status(u), "EXPIRED")

    def test_calendar_expired_active_row_not_overridden_by_newer_rejected(self):
        """Past grace on ACTIVE row: show calendar EXPIRED, not a newer rejected renewal row."""
        today = bd_today()
        now = timezone.now()
        u = User.objects.create_user(
            username="calex",
            email="calex@example.com",
            password="pass",
            is_verified=True,
        )
        active_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.ACTIVE,
            billing_cycle="monthly",
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=10),
            auto_renew=False,
            source=Subscription.Source.MANUAL,
        )
        rejected_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.REJECTED,
            billing_cycle="monthly",
            start_date=today,
            end_date=today + timedelta(days=30),
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        Subscription.objects.filter(pk=active_row.pk).update(
            updated_at=now - timedelta(days=20),
        )
        Subscription.objects.filter(pk=rejected_row.pk).update(
            updated_at=now - timedelta(hours=1),
        )
        cand = get_candidate_subscription_row(u)
        self.assertEqual(cand.pk, active_row.pk)
        self.assertEqual(get_user_subscription_status(u), "EXPIRED")

    def test_rejected_renewal_during_grace_overrides_active_row(self):
        """
        User still has DB ACTIVE (calendar may be GRACE); a newer REJECTED renewal
        attempt must surface REJECTED messaging, not grace/expired copy.
        """
        today = bd_today()
        now = timezone.now()
        u = User.objects.create_user(
            username="grrej",
            email="grrej@example.com",
            password="pass",
            is_verified=True,
        )
        active_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.ACTIVE,
            billing_cycle="monthly",
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=1),
            auto_renew=False,
            source=Subscription.Source.MANUAL,
        )
        rejected_row = Subscription.objects.create(
            user=u,
            plan=self.plan_basic,
            status=Subscription.Status.REJECTED,
            billing_cycle="monthly",
            start_date=today,
            end_date=today + timedelta(days=30),
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        Subscription.objects.filter(pk=active_row.pk).update(
            updated_at=now - timedelta(days=5),
        )
        Subscription.objects.filter(pk=rejected_row.pk).update(
            updated_at=now - timedelta(hours=1),
        )
        cand = get_candidate_subscription_row(u)
        self.assertEqual(cand.pk, rejected_row.pk)
        self.assertEqual(get_user_subscription_status(u), "REJECTED")

    def test_activate_subscription_upgrades_pending_review_linked_payment(self):
        pending = Payment.objects.create(
            user=self.user,
            plan=self.plan_premium,
            subscription=None,
            amount=self.plan_premium.price,
            currency="BDT",
            status=Payment.Status.PENDING,
            provider=Payment.Provider.MANUAL,
            transaction_id=None,
            metadata={},
        )
        today = bd_today()
        pr_sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan_premium,
            status=Subscription.Status.PENDING_REVIEW,
            billing_cycle="monthly",
            start_date=today,
            end_date=today,
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        pending.subscription = pr_sub
        pending.transaction_id = "TXN-UPGRADE-001"
        pending.save(update_fields=["subscription", "transaction_id"])

        sub = activate_subscription(
            self.user,
            self.plan_premium,
            source="payment",
            amount=pending.amount,
            provider=pending.provider,
            existing_pending_payment=pending,
        )
        self.assertEqual(sub.id, pr_sub.id)
        sub.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(pending.status, Payment.Status.SUCCESS)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)

    def test_reject_pending_review_marks_payment_failed(self):
        today = bd_today()
        pr_sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan_premium,
            status=Subscription.Status.PENDING_REVIEW,
            billing_cycle="monthly",
            start_date=today,
            end_date=today,
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        pending = Payment.objects.create(
            user=self.user,
            plan=self.plan_premium,
            subscription=pr_sub,
            amount=self.plan_premium.price,
            currency="BDT",
            status=Payment.Status.PENDING,
            provider=Payment.Provider.MANUAL,
            transaction_id="TXN-REJ-001",
            metadata={},
        )
        reject_pending_review_for_payment(pending)
        pending.refresh_from_db()
        pr_sub.refresh_from_db()
        self.assertEqual(pending.status, Payment.Status.FAILED)
        self.assertEqual(pr_sub.status, Subscription.Status.REJECTED)

    def test_storefront_blocks_at_bd_midnight_end_plus_two(self):
        sub = activate_subscription(
            self.user, self.plan_basic, source="manual", amount=0, provider="manual"
        )
        expected = datetime.combine(sub.end_date + timedelta(days=2), time.min, tzinfo=BD_TZ)
        self.assertEqual(storefront_blocks_at(sub), expected)

    def test_downgrade_clears_order_email_notification_settings(self):
        store = Store.objects.create(
            owner=self.user,
            name="Downgrade Store",
            code=allocate_unique_store_code("DOWNGRADE"),
            owner_name="O",
            owner_email=self.user.email,
        )
        StoreMembership.objects.create(
            user=self.user,
            store=store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )
        ss, _ = StoreSettings.objects.get_or_create(store=store)
        ss.email_notify_owner_on_order_received = True
        ss.email_customer_on_order_confirmed = True
        ss.save()

        activate_subscription(self.user, self.plan_premium, source="manual", amount=0, provider="manual")
        ss.refresh_from_db()
        self.assertFalse(ss.email_notify_owner_on_order_received)

        activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        ss.refresh_from_db()
        self.assertFalse(ss.email_notify_owner_on_order_received)
        self.assertFalse(ss.email_customer_on_order_confirmed)


class FeatureGateTests(TestCase):
    def setUp(self):
        self.plan_basic = Plan.objects.filter(is_default=True).first()
        if not self.plan_basic:
            self.plan_basic = Plan.objects.create(
                name="basic",
                price=0,
                billing_cycle="monthly",
                features=_plan_features(limits={"max_products": 100}),
                is_default=True,
                is_active=True,
            )
        self.plan_premium = Plan.objects.create(
            name="premium",
            price=999,
            billing_cycle="monthly",
            features=_plan_features(
                limits={"max_products": 500},
                features={"basic_analytics": True, "marketing_tools": True},
            ),
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="fguser",
            email="fg@example.com",
            password="pass",
            is_verified=True,
        )

    def test_no_subscription_returns_empty_features(self):
        self.assertFalse(has_feature(self.user, "basic_analytics"))
        self.assertEqual(get_limit(self.user, "max_products"), 0)

    def test_has_feature_returns_true_when_subscription_has_feature(self):
        activate_subscription(self.user, self.plan_premium, source="manual", amount=0, provider="manual")
        self.assertTrue(has_feature(self.user, "basic_analytics"))
        self.assertTrue(has_feature(self.user, "marketing_tools"))
        self.assertEqual(get_limit(self.user, "max_products"), 500)

    def test_get_limit_returns_zero_when_missing(self):
        config = get_feature_config(self.user)
        self.assertEqual(get_limit(self.user, "nonexistent_limit"), 0)

    def test_get_feature_config_returns_structure(self):
        config = get_feature_config(self.user)
        self.assertIn("features", config)
        self.assertIn("limits", config)
        self.assertIsInstance(config["features"], dict)
        self.assertIsInstance(config["limits"], dict)

    def test_require_feature_raises_when_not_allowed(self):
        from rest_framework.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            require_feature(self.user, "marketing_tools")

    def test_require_feature_passes_when_allowed(self):
        activate_subscription(self.user, self.plan_premium, source="manual", amount=0, provider="manual")
        require_feature(self.user, "marketing_tools")

    def test_expired_subscription_row_still_resolves_plan_for_dashboard_features(self):
        """Dashboard keeps last plan limits for UI; storefront is blocked separately."""
        activate_subscription(self.user, self.plan_premium, source="manual", amount=0, provider="manual")
        sub = get_active_subscription(self.user)
        sub.status = Subscription.Status.EXPIRED
        sub.save()
        self.assertTrue(has_feature(self.user, "basic_analytics"))
        self.assertEqual(get_limit(self.user, "max_products"), 500)


class StoreCreationEnforcementTests(TestCase):
    """Verify store creation allows onboarding before plan; one store per owner."""

    def setUp(self):
        self.client = APIClient()
        self.plan_basic = Plan.objects.filter(is_default=True).first()
        if not self.plan_basic:
            self.plan_basic = Plan.objects.create(
                name="basic",
                price=0,
                billing_cycle="monthly",
                features=_plan_features(limits={"max_products": 100}),
                is_default=True,
                is_active=True,
            )
        self.plan_premium = Plan.objects.filter(name="premium").first()
        if not self.plan_premium:
            self.plan_premium = Plan.objects.create(
                name="premium",
                price=999,
                billing_cycle="monthly",
                features=_plan_features(
                    limits={"max_products": 500},
                    features={"basic_analytics": True, "marketing_tools": True},
                ),
                is_active=True,
            )
        self.user = User.objects.create_user(
            username="storeuser",
            email="s@example.com",
            password="pass",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def _create_store_via_api(self, **overrides):
        data = {
            "name": "My Store",
            "owner_first_name": "Owner",
            "owner_last_name": "Name",
            "owner_email": "owner@example.com",
        }
        data.update(overrides)
        return self.client.post(
            "/api/v1/store/",
            data,
            format="json",
            HTTP_HOST="localhost",
        )

    def test_store_creation_allowed_when_no_default_plan_row(self):
        Plan.objects.filter(is_default=True).update(is_default=False)
        try:
            resp = self._create_store_via_api()
            self.assertEqual(resp.status_code, 201)
            self.assertEqual(
                Store.objects.filter(
                    memberships__user=self.user, memberships__role="owner"
                ).count(),
                1,
            )
        finally:
            Plan.objects.filter(name="basic").update(is_default=True)

    def test_store_creation_allowed_without_subscription(self):
        resp = self._create_store_via_api()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            Store.objects.filter(
                memberships__user=self.user, memberships__role="owner"
            ).count(),
            1,
        )

    def test_store_creation_allowed_with_subscription(self):
        activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        resp = self._create_store_via_api()
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Store.objects.filter(memberships__user=self.user, memberships__role="owner").count(), 1)
        self.assertNotIn("api_key", resp.data)
        store_pid = resp.data["public_id"]
        self.assertEqual(StoreApiKey.objects.filter(store__public_id=store_pid).count(), 0)

    def test_second_store_creation_blocked(self):
        activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        self._create_store_via_api()
        resp = self._create_store_via_api(name="Second Store", owner_email="o2@example.com")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already have a store", resp.data.get("detail", ""))


class InitiatePaymentApiTests(TestCase):
    """POST /api/v1/billing/payment/initiate/ — switch plan before paying."""

    def setUp(self):
        self.client = APIClient()
        self.plan_a = Plan.objects.create(
            name="plan_a",
            price=100,
            billing_cycle="monthly",
            features=_plan_features(),
            is_active=True,
        )
        self.plan_b = Plan.objects.create(
            name="plan_b",
            price=250,
            billing_cycle="monthly",
            features=_plan_features(),
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="payuser",
            email="pay@example.com",
            password="pass",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_initiate_twice_before_txn_updates_same_pending(self):
        r1 = self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_a.public_id},
            format="json",
        )
        self.assertEqual(r1.status_code, 201)
        pay_id = r1.data["public_id"]
        self.assertEqual(Decimal(str(r1.data["amount"])), plan_charge_amount(self.plan_a))

        r2 = self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_b.public_id},
            format="json",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["public_id"], pay_id)
        self.assertEqual(r2.data["plan"]["public_id"], self.plan_b.public_id)
        self.assertEqual(Decimal(str(r2.data["amount"])), plan_charge_amount(self.plan_b))
        self.assertEqual(
            Payment.objects.filter(user=self.user, status=Payment.Status.PENDING).count(),
            1,
        )

    def test_initiate_blocked_after_transaction_submitted(self):
        self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_a.public_id},
            format="json",
        )
        self.client.post(
            "/api/v1/billing/payment/submit/",
            {"transaction_id": "TXN-UNIQUE-001", "sender_number": ""},
            format="json",
        )
        r = self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_b.public_id},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("non_field_errors", r.data)


class PendingReviewCheckoutApiTests(TestCase):
    """Payment submit creates PENDING_REVIEW; dashboard and storefront behavior."""

    def setUp(self):
        self.client = APIClient()
        self.plan_paid = Plan.objects.create(
            name="paid_checkout",
            price=Decimal("100.00"),
            billing_cycle="monthly",
            features=_plan_features(limits={"max_products": 50}),
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="prcheckout",
            email="prcheckout@example.com",
            password="pass",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_submit_creates_pending_review_subscription(self):
        self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_paid.public_id},
            format="json",
        )
        r = self.client.post(
            "/api/v1/billing/payment/submit/",
            {"transaction_id": "TXN-PR-CHECKOUT-001", "sender_number": ""},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        pay = Payment.objects.get(user=self.user, status=Payment.Status.PENDING)
        self.assertIsNotNone(pay.subscription_id)
        self.assertEqual(pay.subscription.status, Subscription.Status.PENDING_REVIEW)

    def test_store_creation_succeeds_while_pending_review(self):
        self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_paid.public_id},
            format="json",
        )
        self.client.post(
            "/api/v1/billing/payment/submit/",
            {"transaction_id": "TXN-PR-CHECKOUT-002", "sender_number": ""},
            format="json",
        )
        resp = self.client.post(
            "/api/v1/store/",
            {
                "name": "PR Store",
                "owner_first_name": "A",
                "owner_last_name": "B",
                "owner_email": "a@example.com",
            },
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 201)

    def test_features_endpoint_returns_plan_while_pending_review(self):
        self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_paid.public_id},
            format="json",
        )
        self.client.post(
            "/api/v1/billing/payment/submit/",
            {"transaction_id": "TXN-PR-CHECKOUT-003", "sender_number": ""},
            format="json",
        )
        resp = self.client.get("/api/v1/auth/features/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["limits"].get("max_products"), 50)

    def test_me_subscription_pending_review_no_storefront_blocks_at(self):
        self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_paid.public_id},
            format="json",
        )
        self.client.post(
            "/api/v1/billing/payment/submit/",
            {"transaction_id": "TXN-PR-CHECKOUT-004", "sender_number": ""},
            format="json",
        )
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        sub = resp.data["subscription"]
        self.assertEqual(sub["subscription_status"], "PENDING_REVIEW")
        self.assertIsNone(sub["storefront_blocks_at"])


class FeaturesEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.plan_basic = Plan.objects.filter(is_default=True).first()
        if not self.plan_basic:
            self.plan_basic = Plan.objects.create(
                name="basic",
                price=0,
                billing_cycle="monthly",
                features=_plan_features(limits={"max_products": 100}),
                is_default=True,
                is_active=True,
            )
        self.user = User.objects.create_user(
            username="featuser",
            email="f@example.com",
            password="pass",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_features_endpoint_returns_empty_without_subscription(self):
        resp = self.client.get("/api/v1/auth/features/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("features", resp.data)
        self.assertIn("limits", resp.data)
        self.assertEqual(resp.data["features"], {})
        self.assertEqual(resp.data["limits"], {})

    def test_features_endpoint_returns_config_with_subscription(self):
        activate_subscription(self.user, self.plan_basic, source="manual", amount=0, provider="manual")
        resp = self.client.get("/api/v1/auth/features/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("features", resp.data)
        self.assertIn("limits", resp.data)
        self.assertIn("max_products", resp.data["limits"])

    def test_features_endpoint_200_when_subscription_expired_dashboard(self):
        """Dashboard JWT features stay available; storefront API key is blocked instead."""
        activate_subscription(
            self.user, self.plan_basic, source="manual", amount=0, provider="manual",
        )
        sub = get_active_subscription(self.user)
        self.assertIsNotNone(sub)
        with patch("engine.apps.billing.subscription_status.bd_calendar_date") as m:
            m.return_value = sub.end_date + timedelta(days=2)
            resp = self.client.get("/api/v1/auth/features/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("limits", resp.data)


@override_settings(TENANT_API_KEY_ENFORCE=True)
class StorefrontBlocksWhenOwnerExpiredTests(TestCase):
    """Storefront (public API key) returns subscription_expired when owner plan lapsed."""

    def setUp(self):
        self.plan_basic = Plan.objects.filter(is_default=True).first()
        if not self.plan_basic:
            self.plan_basic = Plan.objects.create(
                name="basic",
                price=0,
                billing_cycle="monthly",
                features=_plan_features(limits={"max_products": 100}),
                is_default=True,
                is_active=True,
            )

    def test_store_public_403_when_owner_subscription_expired(self):
        from engine.apps.stores.services import create_store_api_key
        from tests.apps.stores.test_api_keys import make_store

        store = make_store("ExpiredSF")
        activate_subscription(
            store.owner, self.plan_basic, source="manual", amount=0, provider="manual",
        )
        sub = get_active_subscription(store.owner)
        self.assertIsNotNone(sub)
        _row, raw_key = create_store_api_key(store, name="fe")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
        with patch("engine.apps.billing.subscription_status.bd_calendar_date") as m:
            m.return_value = sub.end_date + timedelta(days=2)
            resp = client.get("/api/v1/store/public/")
        self.assertEqual(resp.status_code, 403)
        body = resp.data if hasattr(resp, "data") else None
        nested = body.get("detail", body) if isinstance(body, dict) else {}
        if isinstance(nested, dict):
            self.assertEqual(nested.get("error"), "subscription_expired")

    def test_store_public_403_when_owner_subscription_pending_review(self):
        from engine.apps.stores.services import create_store_api_key
        from tests.apps.stores.test_api_keys import make_store

        store = make_store("PendingSF")
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=store.owner)
        self.client_api.post(
            "/api/v1/billing/payment/initiate/",
            {
                "plan_public_id": self.plan_basic.public_id,
            },
            format="json",
        )
        self.client_api.post(
            "/api/v1/billing/payment/submit/",
            {"transaction_id": "TXN-PENDING-SF-001", "sender_number": ""},
            format="json",
        )
        _row, raw_key = create_store_api_key(store, name="fe")
        anon = APIClient()
        anon.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
        resp = anon.get("/api/v1/store/public/")
        self.assertEqual(resp.status_code, 403)
        body = resp.data if hasattr(resp, "data") else None
        nested = body.get("detail", body) if isinstance(body, dict) else {}
        if isinstance(nested, dict):
            self.assertEqual(nested.get("error"), "storefront_unavailable")

    def test_store_public_403_when_owner_has_no_subscription(self):
        from engine.apps.stores.services import create_store_api_key
        from tests.apps.stores.test_api_keys import make_store

        store = make_store("NoSubSF")
        _row, raw_key = create_store_api_key(store, name="fe")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
        resp = client.get("/api/v1/store/public/")
        self.assertEqual(resp.status_code, 403)
        body = resp.data if hasattr(resp, "data") else None
        nested = body.get("detail", body) if isinstance(body, dict) else {}
        if isinstance(nested, dict):
            self.assertEqual(nested.get("error"), "STORE_INACTIVE")


@override_settings(TENANT_API_KEY_ENFORCE=True)
class DashboardJwtWithoutSubscriptionTests(TestCase):
    """Dashboard JWT can call admin APIs when the owner has never subscribed."""

    def test_admin_products_list_ok_when_owner_has_no_subscription(self):
        from tests.apps.stores.test_api_keys import make_store

        store = make_store("DashNoSub")
        client = APIClient()
        tok = client.post(
            "/api/v1/auth/token/",
            {"email": store.owner.email, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(tok.status_code, 200, tok.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tok.data['access']}")
        resp = client.get("/api/v1/admin/products/")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))


class MeSubscriptionPayloadTests(TestCase):
    """Verify /auth/me subscription payload includes expiration fields."""

    def setUp(self):
        self.client = APIClient()
        self.plan = Plan.objects.filter(is_default=True).first()
        if not self.plan:
            self.plan = Plan.objects.create(
                name="basic",
                price=0,
                billing_cycle="monthly",
                features=_plan_features(limits={"max_products": 100}),
                is_default=True,
                is_active=True,
            )
        self.user = User.objects.create_user(
            username="meuser",
            email="me@example.com",
            password="pass",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_no_subscription_returns_none_status_with_zero_days(self):
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        sub = resp.data["subscription"]
        self.assertEqual(sub["subscription_status"], "NONE")
        self.assertEqual(sub["days_remaining"], 0)
        self.assertIsNone(sub["plan"])
        self.assertIsNone(sub["plan_public_id"])
        self.assertIsNone(sub["end_date"])
        self.assertIsNone(sub["storefront_blocks_at"])
        self.assertIsNone(resp.data.get("latest_payment_status"))

    def test_active_subscription_returns_days_remaining(self):
        activate_subscription(
            self.user, self.plan, source="manual", amount=0,
            provider="manual", duration_days=30,
        )
        sub_row = get_active_subscription(self.user)
        self.assertIsNotNone(sub_row)
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        sub = resp.data["subscription"]
        self.assertEqual(sub["subscription_status"], "ACTIVE")
        self.assertEqual(sub["days_remaining"], 30)
        self.assertIsNotNone(sub["end_date"])
        self.assertEqual(sub["plan_public_id"], self.plan.public_id)
        expected = storefront_blocks_at(sub_row).isoformat()
        self.assertEqual(sub["storefront_blocks_at"], expected)
        self.assertIsNone(resp.data.get("latest_payment_status"))

    def test_latest_payment_status_rejected_while_subscription_status_expired(self):
        """Latest row by updated_at is REJECTED; candidate status remains EXPIRED."""
        today = bd_today()
        now = timezone.now()
        u = User.objects.create_user(
            username="melps_rej",
            email="melps_rej@example.com",
            password="pass",
            is_verified=True,
        )
        active_row = Subscription.objects.create(
            user=u,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            billing_cycle="monthly",
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=10),
            auto_renew=False,
            source=Subscription.Source.MANUAL,
        )
        rejected_row = Subscription.objects.create(
            user=u,
            plan=self.plan,
            status=Subscription.Status.REJECTED,
            billing_cycle="monthly",
            start_date=today,
            end_date=today + timedelta(days=30),
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        Subscription.objects.filter(pk=active_row.pk).update(
            updated_at=now - timedelta(days=20),
        )
        Subscription.objects.filter(pk=rejected_row.pk).update(
            updated_at=now - timedelta(hours=1),
        )
        self.client.force_authenticate(user=u)
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["subscription"]["subscription_status"], "EXPIRED")
        self.assertEqual(resp.data["latest_payment_status"], "REJECTED")

    def test_latest_payment_status_pending_review(self):
        today = bd_today()
        u = User.objects.create_user(
            username="melps_pend",
            email="melps_pend@example.com",
            password="pass",
            is_verified=True,
        )
        Subscription.objects.create(
            user=u,
            plan=self.plan,
            status=Subscription.Status.PENDING_REVIEW,
            billing_cycle="monthly",
            start_date=today,
            end_date=today,
            auto_renew=False,
            source=Subscription.Source.PAYMENT,
        )
        self.client.force_authenticate(user=u)
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["subscription"]["subscription_status"], "PENDING_REVIEW")
        self.assertEqual(resp.data["latest_payment_status"], "PENDING_REVIEW")


class YearlyPricingAndValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.plan_yearly = Plan.objects.create(
            name="yearly_plan",
            price=Decimal("650.00"),
            billing_cycle="yearly",
            features=_plan_features(),
            is_active=True,
        )
        self.user = User.objects.create_user(
            username="yearlyuser",
            email="yearly@example.com",
            password="pass",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_initiate_payment_yearly_charges_12_months_upfront(self):
        r = self.client.post(
            "/api/v1/billing/payment/initiate/",
            {"plan_public_id": self.plan_yearly.public_id},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(str(r.data["amount"])), Decimal("7800.00"))

    def test_activate_subscription_rejects_payment_amount_mismatch(self):
        with self.assertRaises(ValueError):
            activate_subscription(
                self.user,
                self.plan_yearly,
                source="payment",
                amount=Decimal("650.00"),  # wrong; yearly must be 7800
                provider="manual",
            )

    def test_short_subscription_still_reports_active_status(self):
        activate_subscription(
            self.user,
            self.plan_yearly,
            source="manual",
            amount=0,
            provider="manual",
            duration_days=2,
        )
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        sub = resp.data["subscription"]
        self.assertEqual(sub["subscription_status"], "ACTIVE")
        self.assertEqual(sub["days_remaining"], 2)
        self.assertEqual(sub["plan_public_id"], self.plan_yearly.public_id)
