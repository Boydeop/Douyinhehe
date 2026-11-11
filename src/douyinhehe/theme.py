"""Native Qt desktop design tokens and focused dark theme.

Implementation is plain PySide6 QSS: no GPL widgets, QtWebEngine or browser bundle.
Keep controls readable on 1080p displays and keyboard focus visible.
"""
from __future__ import annotations

COLORS = {
    "background": "#0C111B",
    "surface": "#151D2B",
    "raised": "#1C2838",
    "border": "#344458",
    "text": "#F2F6FC",
    "muted": "#B4C3D4",
    "accent": "#45D4BE",
    "accent_hover": "#7AE4D4",
    "selected": "#174C4C",
    "warning": "#F2B66D",
}

STYLESHEET = """
QMainWindow, QWidget { background: #0C111B; color: #F2F6FC;
    font-family: "Segoe UI"; font-size: 14px; }
QFrame#sidebar { background: #101A29; border-right: 1px solid #344458; }
QLabel#brand { color: #70E3D1; font-size: 21px; font-weight: 800; padding: 7px 0 10px 0; }
QLabel#sidebarCaption { color: #B4C3D4; font-size: 11px; font-weight: 650; }
QLabel#heading { font-size: 24px; font-weight: 750; }
QLabel#pageTitle { font-size: 23px; font-weight: 750; }
QLabel#subheading, QLabel#hintText, QLabel#pageDescription,
QLabel#sidebarFooter, QLabel#sectionDescription {
    color: #B4C3D4; font-size: 13px; }
QLabel#statusPill { border: 1px solid #32665F; border-radius: 11px;
    padding: 5px 12px; background: #163B3A; color: #A5F5E4; font-weight: 650; }
QListWidget#navigation { border: none; background: transparent; outline: none; }
QListWidget#navigation::item { padding: 12px 12px; margin: 3px 0;
    border-radius: 9px; color: #CBD6E4; }
QListWidget#navigation::item:selected { background: #174C4C;
    color: #FFFFFF; border-left: 3px solid #70E3D1; }
QListWidget#navigation::item:hover:!selected { background: #233247; color: #FFFFFF; }
QGroupBox { border: 1px solid #344458; border-radius: 13px;
    margin-top: 20px; padding: 18px 13px 14px 13px;
    font-weight: 650; background: #151D2B; }
QGroupBox::title { subcontrol-origin: margin; left: 13px; top: 2px;
    padding: 0 8px; color: #E8F2FC; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QDateTimeEdit {
    background: #1C2838; color: #F2F6FC; border: 1px solid #465873;
    border-radius: 8px; padding: 9px; selection-background-color: #246F68; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {
    border: 2px solid #70E3D1; }
QComboBox::drop-down { border: none; width: 28px; }
QPushButton { background: #27394E; border: 1px solid #465873;
    border-radius: 9px; padding: 9px 14px; min-height: 28px;
    color: #F2F6FC; font-weight: 650; }
QPushButton:hover { background: #354B63; border-color: #87A0BB; }
QPushButton:pressed { background: #1A5F5D; }
QPushButton:focus { border: 2px solid #90FFE9; }
QPushButton:disabled { background: #1B2633; color: #9DA9B8;
    border-color: #2E3A4A; }
QPushButton#primaryAction { background: #37BFA9; color: #071B22;
    border: 1px solid #5FE0CE; font-weight: 750; }
QPushButton#primaryAction:hover { background: #7AE4D4; }
QPushButton#primaryAction:disabled { background: #23453F; color: #A9C2BE; }
QCheckBox { padding: 7px 2px; spacing: 9px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #151D2B; width: 11px; }
QScrollBar::handle:vertical { background: #50647A; border-radius: 5px; min-height: 20px; }
QProgressBar { border: 1px solid #465873; border-radius: 7px;
    background: #1C2838; text-align: center; min-height: 27px; }
QProgressBar::chunk { background: #45D4BE; border-radius: 6px; }
QSlider::groove:horizontal { height: 7px; background: #45566D; border-radius: 3px; }
QSlider::handle:horizontal { background: #70E3D1; width: 17px;
    margin: -5px 0; border-radius: 8px; }
QToolTip { background: #213047; color: #FFFFFF; border: 1px solid #638399; }
QTabWidget::pane { border: 1px solid #344458; border-radius: 8px; background: #151D2B; }
QTabBar::tab { background: #233247; color: #CFDCEA; border-radius: 7px;
    padding: 10px 12px; margin: 3px; }
QTabBar::tab:selected { background: #174C4C; color: #FFFFFF;
    border-bottom: 2px solid #70E3D1; }
QSplitter::handle { background: #344458; width: 5px; }
QListWidget#clipLibrary { background: #151D2B; border: 1px solid #344458;
    border-radius: 9px; padding: 4px; }
QListWidget#clipLibrary::item { padding: 8px; border-radius: 5px; }
QListWidget#clipLibrary::item:selected { background: #174C4C; color: #FFFFFF; }
"""
