from __future__ import annotations

import logging

from celery import Task, shared_task
from celery.exceptions import MaxRetriesExceededError
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from engine.core.tenant_execution import system_scope
from engine.core.models import ActivityLog

from .invoice_pdf import fetch_order_for_invoice, render_order_invoice_pdf
from .models import Order

logger = logging.getLogger(__name__)


class InvoiceGenerationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            ActivityLog.objects.create(
                action=ActivityLog.Action.CUSTOM,
                entity_type="celery_task",
                entity_id=task_id or "",
                summary="ERROR: invoice generation task failed",
                metadata={
                    "task": self.name,
                    "args": list(args or []),
                    "kwargs": kwargs or {},
                    "error": str(exc),
                },
            )
        except Exception:
            logger.exception("failed to write activity log for invoice task failure")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(
    bind=True,
    max_retries=3,
    base=InvoiceGenerationTask,
    name="engine.apps.orders.generate_order_invoice_pdf",
)
def generate_order_invoice_pdf(self, order_id: str, store_id: int) -> None:
    lock_key = f"invoice_generating:{order_id}"
    if not cache.add(lock_key, 1, timeout=300):
        return
    try:
        with system_scope(reason="generate_order_invoice_pdf"):
            order = fetch_order_for_invoice(order_id=order_id)
            if order.store_id != int(store_id):
                logger.error(
                    "invoice_pdf_store_mismatch",
                    extra={"order_id": order_id, "store_id": store_id},
                )
                return
            payload = render_order_invoice_pdf(order=order)
            with transaction.atomic():
                locked = Order.objects.select_for_update().get(id=order.id, store_id=store_id)
                locked.pdf_file.save(payload.filename, ContentFile(payload.content), save=False)
                locked.pdf_generated_at = timezone.now()
                locked.save(update_fields=["pdf_file", "pdf_generated_at", "updated_at"])
                cache.set(f"invoice_ready:{locked.public_id}", 1, 3600)
    except Exception as exc:
        logger.exception(
            "invoice_pdf_generation_failed",
            extra={"order_id": order_id, "store_id": store_id},
        )
        countdown = 2 ** (self.request.retries + 1)
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(
                "invoice_pdf_generation_max_retries",
                extra={"order_id": order_id, "store_id": store_id},
            )
            return
    finally:
        cache.delete(lock_key)
