"""Compatibility facade for the native Qt palette.

The single source of styling is ui_theme.py. Keep the legacy names while
allowing light and dark mode without duplicating hard-coded QSS.
"""
from __future__ import annotations

from .ui_theme import PALETTES, theme_stylesheet

COLORS = {**PALETTES["dark"], "background": PALETTES["dark"]["canvas"]}
STYLESHEET = theme_stylesheet("dark")
