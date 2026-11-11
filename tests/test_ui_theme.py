"""Regression tests for the dependency-free desktop theme and accessibility."""
from __future__ import annotations

import pytest

from douyinhehe.ui_theme import PALETTES, theme_stylesheet


def _luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
              for c in channels]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))


def _contrast(first: str, second: str) -> float:
    a, b = sorted((_luminance(first), _luminance(second)))
    return (b + .05) / (a + .05)


@pytest.mark.parametrize("mode", ("dark", "light"))
def test_theme_has_complete_qt_selectors(mode):
    css = theme_stylesheet(mode)
    for selector in ("QListWidget#navigation", "QGroupBox", "QPushButton#primaryAction",
                     "QLabel#statusPill", "QListWidget#clipLibrary",
                     "QLineEdit:focus", "QLabel#heading", "QSlider::handle:horizontal"):
        assert selector in css
    assert "%(" not in css, "Unexpanded palette token in Qt stylesheet"
    assert len(css) > 2000


@pytest.mark.parametrize("mode", ("dark", "light"))
def test_theme_text_contrast_at_least_wcag_aa(mode):
    colors = PALETTES[mode]
    assert _contrast(colors["text"], colors["canvas"]) >= 4.5
    assert _contrast(colors["muted"], colors["canvas"]) >= 4.5
    assert _contrast(colors["accent_text"], colors["accent"]) >= 4.5


def test_unknown_theme_is_rejected():
    with pytest.raises(ValueError, match="dark"):
        theme_stylesheet("invalid")


def test_all_ui_action_callbacks_exist():
    """Prevent Qt startup crashes when a removed editor callback survives in Settings."""
    from pathlib import Path
    import re

    source = (Path(__file__).parents[1] / "src" / "douyinhehe" / "app.py").read_text(
        encoding="utf-8"
    )
    used = set(re.findall(r"self\.(on_[a-zA-Z_]\w*)", source))
    defined = set(re.findall(r"\bdef\s+(on_[a-zA-Z_]\w*)\s*\(", source))
    assert used <= defined, f"Unimplemented UI actions: {sorted(used - defined)}"
