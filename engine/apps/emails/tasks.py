from __future__ import annotations

from config.celery import app
from engine.core.tenant_execution import system_scope

from .services import send_email


@app.task(name="engine.apps.emails.send_email")
def send_email_task(
    email_type: str,
    to_email: str,
    context: dict | None = None,
    from_email: str | None = None,
):
    with system_scope(reason="send_email_task"):
        send_email(email_type, to_email, context or {}, from_email=from_email)
