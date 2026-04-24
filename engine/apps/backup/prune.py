"""
Time-batched deletion of non-critical tables before physical base backups.

Physical pg_basebackup cannot exclude tables; this module caps heap growth at the source.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from django.db import models
from django.utils import timezone

from engine.core.tenant_execution import system_scope

logger = logging.getLogger(__name__)


def _delete_in_batches(*, model: type[models.Model], qs: models.QuerySet, batch_size: int) -> int:
    """Delete rows matching ``qs`` in batches of primary keys. Returns approximate row delete count."""
    total = 0
    while True:
        pks = list(qs.values_list("pk", flat=True)[:batch_size])
        if not pks:
            break
        deleted, _ = model.objects.filter(pk__in=pks).delete()
        total += int(deleted or 0)
    return total


def prune_noncritical_tables() -> dict[str, int]:
    """
    Idempotent retention deletes for backup-adjacent noise tables.

    Runs under ``system_scope`` so tenant-scoped models (e.g. FraudCheckLog) can be pruned
    from Celery without a store context.
    """
    if not getattr(settings, "BACKUP_PRUNE_ENABLED", True):
        logger.info("backup_prune skipped (BACKUP_PRUNE_ENABLED is false)")
        return {}

    batch = int(getattr(settings, "BACKUP_PRUNE_BATCH_SIZE", 500))
    now = timezone.now()
    today = now.date()
    counts: dict[str, int] = {}

    with system_scope(reason="backup_table_prune"):
        # django_session — only expired sessions (same idea as clearsessions).
        expired_sessions = Session.objects.filter(expire_date__lt=now)
        counts["django_session"] = _delete_in_batches(
            model=Session, qs=expired_sessions.order_by("pk"), batch_size=batch
        )

        # django_admin_log
        admin_cutoff = now - timedelta(days=int(settings.BACKUP_PRUNE_ADMIN_LOG_DAYS))
        admin_qs = LogEntry.objects.filter(action_time__lt=admin_cutoff).order_by("pk")
        counts["django_admin_log"] = _delete_in_batches(model=LogEntry, qs=admin_qs, batch_size=batch)

        # core_activitylog
        from engine.core.models import ActivityLog

        act_cutoff = now - timedelta(days=int(settings.BACKUP_PRUNE_ACTIVITY_LOG_DAYS))
        act_qs = ActivityLog.objects.filter(created_at__lt=act_cutoff).order_by("pk")
        counts["core_activitylog"] = _delete_in_batches(model=ActivityLog, qs=act_qs, batch_size=batch)

        # emails_emaillog
        from engine.apps.emails.models import EmailLog

        email_cutoff = now - timedelta(days=int(settings.BACKUP_PRUNE_EMAIL_LOG_DAYS))
        email_qs = EmailLog.objects.filter(created_at__lt=email_cutoff).order_by("pk")
        counts["emails_emaillog"] = _delete_in_batches(model=EmailLog, qs=email_qs, batch_size=batch)

        # fraud_check_fraudchecklog
        from engine.apps.fraud_check.models import FraudCheckLog

        fraud_cutoff = now - timedelta(days=int(settings.BACKUP_PRUNE_FRAUD_CHECK_LOG_DAYS))
        fraud_qs = FraudCheckLog.objects.filter(checked_at__lt=fraud_cutoff).order_by("pk")
        counts["fraud_check_fraudchecklog"] = _delete_in_batches(
            model=FraudCheckLog, qs=fraud_qs, batch_size=batch
        )

        # marketing_integrations_storeeventlog (all apps; complements tracking-only periodic task)
        from engine.apps.marketing_integrations.models import StoreEventLog

        hours = max(1, int(settings.BACKUP_PRUNE_STORE_EVENT_LOG_HOURS))
        event_cutoff = now - timedelta(hours=hours)
        event_qs = StoreEventLog.objects.filter(created_at__lt=event_cutoff).order_by("pk")
        counts["marketing_integrations_storeeventlog"] = _delete_in_batches(
            model=StoreEventLog, qs=event_qs, batch_size=batch
        )

        # notifications_notificationdismissal
        from engine.apps.notifications.models import NotificationDismissal

        dismiss_cutoff_date = today - timedelta(days=int(settings.BACKUP_PRUNE_NOTIFICATION_DISMISSAL_DAYS))
        dismiss_qs = NotificationDismissal.objects.filter(date__lt=dismiss_cutoff_date).order_by("pk")
        counts["notifications_notificationdismissal"] = _delete_in_batches(
            model=NotificationDismissal, qs=dismiss_qs, batch_size=batch
        )

        # analytics_storedashboardstatssnapshot
        from engine.apps.basic_analytics.models import StoreDashboardStatsSnapshot

        snap_cutoff = today - timedelta(days=int(settings.BACKUP_PRUNE_DASHBOARD_SNAPSHOT_DAYS))
        snap_qs = StoreDashboardStatsSnapshot.objects.filter(end_date__lt=snap_cutoff).order_by("pk")
        counts["analytics_storedashboardstatssnapshot"] = _delete_in_batches(
            model=StoreDashboardStatsSnapshot, qs=snap_qs, batch_size=batch
        )

        # orders_orderexportjob — terminal rows only
        from engine.apps.orders.models import OrderExportJob

        export_cutoff = now - timedelta(days=int(settings.BACKUP_PRUNE_ORDER_EXPORT_JOB_DAYS))
        export_qs = (
            OrderExportJob.objects.filter(
                updated_at__lt=export_cutoff,
                status__in=(OrderExportJob.Status.EXPIRED, OrderExportJob.Status.FAILED),
            )
            .order_by("pk")
        )
        counts["orders_orderexportjob"] = _delete_in_batches(
            model=OrderExportJob, qs=export_qs, batch_size=batch
        )

    non_zero = {k: v for k, v in counts.items() if v}
    if non_zero:
        logger.info("backup_prune completed", extra={"deleted_by_table": non_zero})
    else:
        logger.info("backup_prune completed (no rows matched cutoffs)")
    return counts


def prune_summary(counts: dict[str, int]) -> str:
    parts = [f"{k}={v}" for k, v in sorted(counts.items()) if v]
    return ", ".join(parts) if parts else "(none)"
