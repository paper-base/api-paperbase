"""Centralized sender routing by email type."""

from __future__ import annotations

from .constants import (
    EMAIL_VERIFICATION,
    GENERIC_NOTIFICATION,
    ORDER_CONFIRMED,
    ORDER_RECEIVED,
    PASSWORD_RESET,
    PLATFORM_NEW_SUBSCRIPTION,
    SUBSCRIPTION_ACTIVATED,
    SUBSCRIPTION_CHANGED,
    SUBSCRIPTION_PAYMENT,
    TWO_FA_DISABLE,
    TWO_FA_RECOVERY,
)

DEFAULT_SENDER = "noreply@mail.paperbase.me"

EMAIL_SENDER_MAP: dict[str, str] = {
    PASSWORD_RESET: "security@mail.paperbase.me",
    EMAIL_VERIFICATION: "security@mail.paperbase.me",
    TWO_FA_RECOVERY: "security@mail.paperbase.me",
    TWO_FA_DISABLE: "security@mail.paperbase.me",
    SUBSCRIPTION_PAYMENT: "billing@mail.paperbase.me",
    SUBSCRIPTION_ACTIVATED: "billing@mail.paperbase.me",
    SUBSCRIPTION_CHANGED: "billing@mail.paperbase.me",
    PLATFORM_NEW_SUBSCRIPTION: "billing@mail.paperbase.me",
    ORDER_CONFIRMED: "noreply@mail.paperbase.me",
    ORDER_RECEIVED: "noreply@mail.paperbase.me",
    GENERIC_NOTIFICATION: "noreply@mail.paperbase.me",
}


def resolve_email_sender(email_type: str) -> str:
    """
    Return sender identity for a template type.

    Always returns a Paperbase sender and never an empty value.
    """
    normalized = (email_type or "").strip()
    sender = EMAIL_SENDER_MAP.get(normalized, DEFAULT_SENDER)
    if not sender:
        return DEFAULT_SENDER
    return sender
