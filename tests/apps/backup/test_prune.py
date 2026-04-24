"""Tests for pre-backup non-critical table pruning."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from django.utils import timezone

from engine.apps.backup.prune import prune_noncritical_tables, prune_summary
from engine.apps.emails.models import EmailLog
from engine.apps.stores.models import Store

User = get_user_model()


class PruneNoncriticalTablesTests(TestCase):
    def test_prune_disabled_returns_empty(self):
        with override_settings(BACKUP_PRUNE_ENABLED=False):
            self.assertEqual(prune_noncritical_tables(), {})

    def test_prune_summary_empty(self):
        self.assertEqual(prune_summary({}), "(none)")

    def test_prune_summary_nonzero(self):
        s = prune_summary({"emails_emaillog": 3, "django_session": 1})
        self.assertIn("django_session=1", s)
        self.assertIn("emails_emaillog=3", s)

    @override_settings(BACKUP_PRUNE_EMAIL_LOG_DAYS=7, BACKUP_PRUNE_BATCH_SIZE=50)
    def test_old_email_logs_deleted(self):
        user = User.objects.create_user(email="prune-a@example.com", password="x", is_verified=True)
        store = Store.objects.create(
            owner=user,
            name="S",
            code="PRNE1",
            owner_name="O",
            owner_email=user.email,
        )
        old = timezone.now() - timedelta(days=30)
        log = EmailLog.objects.create(
            store=store,
            to_email="a@b.com",
            type="TEST",
            status=EmailLog.Status.SENT,
        )
        EmailLog.objects.filter(pk=log.pk).update(created_at=old)

        prune_noncritical_tables()
        self.assertFalse(EmailLog.objects.exists())

    @override_settings(BACKUP_PRUNE_EMAIL_LOG_DAYS=7, BACKUP_PRUNE_BATCH_SIZE=50)
    def test_recent_email_logs_kept(self):
        user = User.objects.create_user(email="prune-b@example.com", password="x", is_verified=True)
        store = Store.objects.create(
            owner=user,
            name="S2",
            code="PRNE2",
            owner_name="O2",
            owner_email=user.email,
        )
        EmailLog.objects.create(
            store=store,
            to_email="c@d.com",
            type="TEST",
            status=EmailLog.Status.SENT,
        )
        prune_noncritical_tables()
        self.assertEqual(EmailLog.objects.count(), 1)

    @override_settings(BACKUP_PRUNE_BATCH_SIZE=50)
    def test_expired_sessions_deleted_only(self):
        now = timezone.now()
        Session.objects.create(
            session_key="old_sess",
            session_data="{}",
            expire_date=now - timedelta(days=1),
        )
        Session.objects.create(
            session_key="new_sess",
            session_data="{}",
            expire_date=now + timedelta(days=1),
        )
        prune_noncritical_tables()
        self.assertFalse(Session.objects.filter(session_key="old_sess").exists())
        self.assertTrue(Session.objects.filter(session_key="new_sess").exists())
