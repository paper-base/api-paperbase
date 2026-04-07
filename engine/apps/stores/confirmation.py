"""Server-side text confirmation for destructive store actions (must match dashboard)."""

DELETE_STORE_CONFIRM_PHRASE = "delete my store"
REMOVE_STORE_CONFIRM_PHRASE = "remove my store"


def confirm_delete_phrase(value: str | None) -> bool:
    return (value or "").strip() == DELETE_STORE_CONFIRM_PHRASE


def confirm_remove_phrase(value: str | None) -> bool:
    return (value or "").strip() == REMOVE_STORE_CONFIRM_PHRASE


def confirm_store_name(value: str | None, store_name: str) -> bool:
    return (value or "").strip() == (store_name or "").strip()


def confirm_store_name_against_store(value: str | None, store) -> bool:
    return confirm_store_name(value, getattr(store, "name", "") or "")
