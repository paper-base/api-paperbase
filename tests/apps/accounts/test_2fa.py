from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from engine.apps.accounts.models import UserTwoFactor
from engine.apps.emails.constants import TWO_FA_RECOVERY
from engine.apps.stores.models import Store, StoreMembership
from engine.apps.stores.services import allocate_unique_store_code

User = get_user_model()


class TwoFactorFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="owner@2fa.local", password="pass1234", is_verified=True)
        self.store = Store.objects.create(
            owner=self.user,
            name="2FA Store",
            code=allocate_unique_store_code("TWOFASTOR"),
            owner_name="Owner",
            owner_email="owner@2fa.local",
        )
        StoreMembership.objects.create(
            user=self.user,
            store=self.store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )

    def _login(self):
        resp = self.client.post(
            "/api/v1/auth/token/",
            {"email": self.user.email, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    def test_enable_2fa_then_login_requires_challenge(self):
        self._login()

        setup_resp = self.client.get("/api/v1/auth/2fa/setup/")
        self.assertEqual(setup_resp.status_code, 200)
        self.assertIn("secret", setup_resp.data)
        otp = pyotp.TOTP(setup_resp.data["secret"]).now()

        verify_resp = self.client.post("/api/v1/auth/2fa/verify/", {"code": otp}, format="json")
        self.assertEqual(verify_resp.status_code, 200)
        self.assertTrue(verify_resp.data["is_enabled"])
        self.assertNotIn("id", verify_resp.data)

        self.client.credentials()
        login_resp = self.client.post(
            "/api/v1/auth/token/",
            {"email": self.user.email, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 202)
        self.assertTrue(login_resp.data["2fa_required"])
        self.assertIn("challenge_public_id", login_resp.data)
        self.assertNotIn("challenge_id", login_resp.data)
        self.assertNotIn("access", login_resp.data)

    def test_challenge_verify_issues_tokens(self):
        profile, _ = UserTwoFactor.objects.get_or_create(user=self.user)
        secret = pyotp.random_base32()
        profile.secret = secret
        profile.is_enabled = True
        profile.save(update_fields=["secret_encrypted", "is_enabled", "updated_at"])

        login_resp = self.client.post(
            "/api/v1/auth/token/",
            {"email": self.user.email, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 202)
        challenge_public_id = login_resp.data["challenge_public_id"]

        otp = pyotp.TOTP(secret).now()
        verify_resp = self.client.post(
            "/api/v1/auth/2fa/challenge/verify/",
            {"challenge_public_id": challenge_public_id, "code": otp},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, 200)
        self.assertIn("access", verify_resp.data)
        self.assertIn("refresh", verify_resp.data)

    def test_disable_requires_password_and_otp(self):
        self._login()
        profile, _ = UserTwoFactor.objects.get_or_create(user=self.user)
        secret = pyotp.random_base32()
        profile.secret = secret
        profile.is_enabled = True
        profile.save(update_fields=["secret_encrypted", "is_enabled", "updated_at"])

        bad_resp = self.client.post(
            "/api/v1/auth/2fa/disable/",
            {"password": "wrong", "code": "123456"},
            format="json",
        )
        self.assertEqual(bad_resp.status_code, 400)

        good_resp = self.client.post(
            "/api/v1/auth/2fa/disable/",
            {"password": "pass1234", "code": pyotp.TOTP(secret).now()},
            format="json",
        )
        self.assertEqual(good_resp.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.is_enabled)

    def test_challenge_verify_rejects_non_totp_code(self):
        profile, _ = UserTwoFactor.objects.get_or_create(user=self.user)
        secret = pyotp.random_base32()
        profile.secret = secret
        profile.is_enabled = True
        profile.save(update_fields=["secret_encrypted", "is_enabled", "updated_at"])

        login_resp = self.client.post(
            "/api/v1/auth/token/",
            {"email": self.user.email, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 202)
        challenge_public_id = login_resp.data["challenge_public_id"]

        bad_verify = self.client.post(
            "/api/v1/auth/2fa/challenge/verify/",
            {"challenge_public_id": challenge_public_id, "code": "ABCD-1234"},
            format="json",
        )
        self.assertEqual(bad_verify.status_code, 400)


class TwoFactorRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(email="owner@rec.local", password="pass1234", is_verified=True)
        self.store = Store.objects.create(
            owner=self.user,
            name="Rec Store",
            code=allocate_unique_store_code("RECSTORE"),
            owner_name="Owner",
            owner_email="owner@rec.local",
        )
        StoreMembership.objects.create(
            user=self.user,
            store=self.store,
            role=StoreMembership.Role.OWNER,
            is_active=True,
        )

    def _auth(self):
        resp = self.client.post(
            "/api/v1/auth/token/",
            {"email": self.user.email, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    def _enable_2fa(self):
        profile, _ = UserTwoFactor.objects.get_or_create(user=self.user)
        secret = pyotp.random_base32()
        profile.secret = secret
        profile.is_enabled = True
        profile.save(update_fields=["secret_encrypted", "is_enabled", "updated_at"])
        return secret

    @patch("engine.apps.emails.tasks.send_email_task.delay")
    def test_recovery_request_sends_email(self, mock_delay):
        self._auth()
        self._enable_2fa()

        resp = self.client.post("/api/v1/auth/2fa/recovery/request/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args[0][0], TWO_FA_RECOVERY)

    def test_recovery_request_fails_when_2fa_disabled(self):
        self._auth()
        resp = self.client.post("/api/v1/auth/2fa/recovery/request/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("engine.apps.emails.tasks.send_email_task.delay")
    def test_recovery_verify_disables_2fa(self, mock_delay):
        self._auth()
        self._enable_2fa()

        self.client.post(
            "/api/v1/auth/2fa/recovery/request/",
            {},
            format="json",
            REMOTE_ADDR="10.1.0.1",
        )
        plain_code = mock_delay.call_args[0][2]["code"]

        mock_delay.reset_mock()
        verify = self.client.post(
            "/api/v1/auth/2fa/recovery/verify/",
            {"code": plain_code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        self.assertFalse(verify.data["is_enabled"])
        profile = UserTwoFactor.objects.get(user=self.user)
        self.assertFalse(profile.is_enabled)
        self.assertTrue(mock_delay.called)

        second = self.client.post(
            "/api/v1/auth/2fa/recovery/verify/",
            {"code": plain_code},
            format="json",
        )
        self.assertEqual(second.status_code, 400)
