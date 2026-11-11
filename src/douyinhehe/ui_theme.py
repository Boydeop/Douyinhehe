"""Lightweight native Qt design system for the Douyinhehe desktop studio.

No remote assets, web runtime, or third-party widget license dependencies.
The token set is deliberately shared across all nine workspace pages.
"""
from __future__ import annotations

PALETTES = {
    "dark": {
        "canvas": "#0B1020",
        "surface": "#111827",
        "surface2": "#182236",
        "sidebar": "#0D1424",
        "field": "#1B273A",
        "border": "#34445D",
        "hover": "#26364E",
        "text": "#F1F5FB",
        "muted": "#B7C5D8",
        "accent": "#45D4BE",
        "accent_hover": "#7AE4D4",
        "accent_text": "#071B22",
        "selected": "#174C4C",
        "success": "#83E0B4",
    },
    "light": {
        "canvas": "#F2F5FA",
        "surface": "#FFFFFF",
        "surface2": "#F7F9FD",
        "sidebar": "#E9EDF5",
        "field": "#FFFFFF",
        "border": "#B2BFD1",
        "hover": "#DFE7F2",
        "text": "#172238",
        "muted": "#41526B",
        "accent": "#AF4F30",
        "accent_hover": "#914025",
        "accent_text": "#FFFFFF",
        "selected": "#F8E6DF",
        "success": "#156E53",
    },
}


def theme_stylesheet(mode: str = "dark") -> str:
    """Return Qt stylesheet using the same hierarchy in both themes."""
    if mode not in PALETTES:
        raise ValueError("Giao diện chỉ hỗ trợ dark hoặc light.")
    c = PALETTES[mode]
    return """
        QMainWindow, QWidget#workspaceRoot { background: %(canvas)s; }
        QWidget { color: %(text)s; font-family: "Segoe UI"; font-size: 14px; }
        QFrame#sidebar { background: %(sidebar)s; border-right: 1px solid %(border)s; }
        QLabel#brand { color: %(accent)s; font-size: 21px; font-weight: 800; padding: 4px 0 2px 0; }
        QLabel#sidebarCaption { color: %(muted)s; font-size: 11px; letter-spacing: 1px; }
        QLabel#navSection, QLabel#eyebrow {
            color: %(muted)s; font-size: 11px; font-weight: 700; padding: 6px 2px;
        }
        QLabel#sidebarFooter { color: %(muted)s; font-size: 12px; }
        QLabel#heading { color: %(text)s; font-size: 25px; font-weight: 800; padding: 0px; }
        QLabel#subheading, QLabel#hintText, QLabel#pageDescription {
            color: %(muted)s; font-size: 13px; padding: 3px 0;
        }
        QLabel#pageTitle { color: %(text)s; font-size: 21px; font-weight: 750; padding: 2px; }
        QLabel#statusPill {
            color: %(success)s; background: %(surface2)s;
            border: 1px solid %(border)s; border-radius: 11px;
            padding: 7px 10px; font-size: 12px; font-weight: 650;
        }
        QListWidget#navigation {
            border: none; background: transparent; outline: none;
        }
        QListWidget#navigation::item {
            padding: 12px 11px; margin: 3px 0;
            border-radius: 9px; color: %(text)s;
        }
        QListWidget#navigation::item:selected {
            background: %(selected)s; color: %(text)s;
            border-left: 3px solid %(accent)s;
        }
        QListWidget#navigation::item:hover:!selected { background: %(hover)s; }
        QGroupBox {
            color: %(text)s; border: 1px solid %(border)s; border-radius: 13px;
            margin-top: 19px; padding: 17px 14px 13px 14px;
            background: %(surface)s; font-weight: 650;
        }
        QGroupBox::title {
            subcontrol-origin: margin; left: 14px; top: 3px;
            padding: 0 8px; background: %(surface)s; color: %(text)s;
        }
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox,
        QSpinBox, QDoubleSpinBox, QDateTimeEdit {
            color: %(text)s; background: %(field)s;
            border: 1px solid %(border)s; border-radius: 8px;
            padding: 8px; selection-background-color: %(accent)s;
        }
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
        QDateTimeEdit:focus {
            border: 2px solid %(accent)s;
        }
        QComboBox::drop-down { width: 26px; border: none; }
        QPushButton {
            color: %(text)s; background: %(surface2)s;
            border: 1px solid %(border)s; border-radius: 9px;
            padding: 9px 13px; min-height: 29px; font-weight: 650;
        }
        QPushButton:hover { background: %(hover)s; border: 1px solid %(muted)s; }
        QPushButton:focus { border: 2px solid %(accent)s; }
        QPushButton#primaryAction {
            color: %(accent_text)s; background: %(accent)s;
            border: 1px solid %(accent)s; font-weight: 800;
        }
        QPushButton#primaryAction:hover {
            background: %(accent_hover)s; border-color: %(accent_hover)s;
        }
        QPushButton#quietAction { background: transparent; border: 1px solid %(border)s; }
        QPushButton:disabled { color: %(muted)s; background: %(canvas)s; border-color: %(border)s; }
        QCheckBox { padding: 8px 3px; spacing: 10px; }
        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical { background: %(canvas)s; width: 12px; margin: 0; }
        QScrollBar::handle:vertical {
            background: %(border)s; border-radius: 6px; min-height: 32px;
        }
        QProgressBar {
            color: %(text)s; background: %(surface2)s; border: 1px solid %(border)s;
            border-radius: 8px; text-align: center; min-height: 29px;
        }
        QProgressBar::chunk { background: %(accent)s; border-radius: 7px; }
        QSlider::groove:horizontal { height: 7px; background: %(border)s; border-radius: 3px; }
        QSlider::handle:horizontal {
            width: 17px; background: %(accent)s; margin: -5px 0; border-radius: 7px;
        }
        QTabWidget::pane {
            background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px;
        }
        QTabBar::tab {
            color: %(muted)s; background: %(surface2)s;
            padding: 11px 13px; margin: 3px; border-radius: 7px;
        }
        QTabBar::tab:selected {
            color: %(text)s; background: %(selected)s;
            border-bottom: 2px solid %(accent)s;
        }
        QSplitter::handle { background: %(border)s; width: 5px; }
        QListWidget {
            color: %(text)s; background: %(surface2)s;
            border: 1px solid %(border)s; border-radius: 9px;
        }
        QListWidget::item { padding: 9px; border-radius: 6px; }
        QListWidget::item:selected { background: %(selected)s; color: %(text)s; }
        QListWidget#clipLibrary { background: %(surface2)s; border: 1px solid %(border)s; }\n        QToolTip {
            color: %(text)s; background: %(surface2)s;
            border: 1px solid %(border)s; padding: 6px;
        }
    """ % c
