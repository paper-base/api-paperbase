"""DiceBear avatar URL — matches dash-paperbase/src/lib/avatar.ts getAvatarUrl."""

from __future__ import annotations

from urllib.parse import quote


def dicebear_avatar_url(seed: str) -> str:
    """Return SVG avatar URL; seed must be non-empty (caller supplies public_id fallback)."""
    encoded = quote(str(seed), safe="")
    return (
        "https://api.dicebear.com/9.x/thumbs/svg"
        f"?seed={encoded}&fontWeight=600&fontSize=42"
    )
