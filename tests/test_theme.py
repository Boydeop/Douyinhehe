"""Native QSS contract: no external UI runtime and visible keyboard focus."""
from douyinhehe.theme import COLORS, STYLESHEET


def test_theme_has_readable_controls_and_keyboard_focus():
    assert STYLESHEET.count("{") == STYLESHEET.count("}")
    assert "QPushButton:focus" in STYLESHEET
    assert "QLineEdit:focus" in STYLESHEET
    assert "QListWidget#navigation::item:selected" in STYLESHEET
    assert "QPushButton:disabled" in STYLESHEET
    assert "QLabel#statusPill" in STYLESHEET


def test_core_color_palette_has_valid_hex_codes():
    import re
    assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", value) for value in COLORS.values())


def test_foreground_background_contrast_is_accessible():
    def luminance(color):
        values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
    foreground, background = luminance(COLORS["text"]), luminance(COLORS["surface"])
    ratio = (max(foreground, background) + .05) / (min(foreground, background) + .05)
    assert ratio >= 7.0
