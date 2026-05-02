"""
Single source of truth for storefront color palettes. Do not duplicate elsewhere.
"""

from __future__ import annotations

PALETTES: dict[str, dict[str, str]] = {
    "ivory": {
        "background": "#FAFAF8",
        "foreground": "#1A1A1A",
        "primary": "#1A1A1A",
        "primary_foreground": "#FAFAF8",
        "secondary": "#F0EFEA",
        "secondary_foreground": "#1A1A1A",
        "muted": "#F0EFEA",
        "muted_foreground": "#6B6B6B",
        "accent": "#C9A96E",
        "accent_foreground": "#1A1A1A",
        "card": "#F0EFEA",
        "card_foreground": "#1A1A1A",
        "popover": "#F0EFEA",
        "popover_foreground": "#1A1A1A",
        "border": "#E5E4DF",
        "input": "#E5E4DF",
        "ring": "#C9A96E",
    },
    "obsidian": {
        "background": "#0F0F0F",
        "foreground": "#EDEDED",
        "primary": "#EDEDED",
        "primary_foreground": "#0F0F0F",
        "secondary": "#1A1A1A",
        "secondary_foreground": "#EDEDED",
        "muted": "#1A1A1A",
        "muted_foreground": "#A0A0A0",
        "accent": "#C9A96E",
        "accent_foreground": "#0F0F0F",
        "card": "#1A1A1A",
        "card_foreground": "#EDEDED",
        "popover": "#1A1A1A",
        "popover_foreground": "#EDEDED",
        "border": "#2A2A2A",
        "input": "#2A2A2A",
        "ring": "#C9A96E",
    },
    "arctic": {
        "background": "#F8FAFC",
        "foreground": "#0F172A",
        "primary": "#0F172A",
        "primary_foreground": "#F8FAFC",
        "secondary": "#F1F5F9",
        "secondary_foreground": "#0F172A",
        "muted": "#F1F5F9",
        "muted_foreground": "#64748B",
        "accent": "#3B82F6",
        "accent_foreground": "#F8FAFC",
        "card": "#F1F5F9",
        "card_foreground": "#0F172A",
        "popover": "#F1F5F9",
        "popover_foreground": "#0F172A",
        "border": "#E2E8F0",
        "input": "#E2E8F0",
        "ring": "#3B82F6",
    },
    "sage": {
        "background": "#F6F7F4",
        "foreground": "#2D3B2D",
        "primary": "#2D3B2D",
        "primary_foreground": "#F6F7F4",
        "secondary": "#ECEEE8",
        "secondary_foreground": "#2D3B2D",
        "muted": "#ECEEE8",
        "muted_foreground": "#6B7A6B",
        "accent": "#8FAF6E",
        "accent_foreground": "#2D3B2D",
        "card": "#ECEEE8",
        "card_foreground": "#2D3B2D",
        "popover": "#ECEEE8",
        "popover_foreground": "#2D3B2D",
        "border": "#DDE0D8",
        "input": "#DDE0D8",
        "ring": "#8FAF6E",
    },
}

DEFAULT_PALETTE = "ivory"
PALETTE_CHOICES = list(PALETTES.keys())

PALETTE_LABELS: dict[str, str] = {
    "ivory": "Ivory",
    "obsidian": "Obsidian",
    "arctic": "Arctic",
    "sage": "Sage",
}


def resolve_palette(palette_key: str) -> dict[str, str]:
    key = (palette_key or "").strip().lower()
    if key not in PALETTES:
        key = DEFAULT_PALETTE
    raw = PALETTES[key]
    return {k.replace("_", "-"): v for k, v in raw.items()}
