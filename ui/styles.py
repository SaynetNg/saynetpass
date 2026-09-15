"""Theme definitions (dark / light), QSS stylesheets, and the app icon.

The icon uses the project logo image (`b.png`); if the file is missing, a
programmatically drawn shield + padlock fallback is used instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from string import Template

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QPainter, QPen, QPixmap

if getattr(sys, "frozen", False):  # PyInstaller bundle
    _PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent

LOGO_PATH = _PROJECT_ROOT / "b.png"

DARK = {
    "bg": "#121212",
    "panel": "#1E1E1E",
    "panel_light": "#262626",
    "accent": "#6C63FF",
    "accent_hover": "#7D75FF",
    "text": "#FFFFFF",
    "muted": "#A0A0A0",
    "danger": "#E74C3C",
    "danger_hover": "#F05A4B",
    "success": "#2ECC71",
    "border": "#333333",
    "input_bg": "#181818",
    "input_border": "#3A3A3A",
    "selection": "#2A2A40",
}

LIGHT = {
    "bg": "#F5F6FA",
    "panel": "#FFFFFF",
    "panel_light": "#E9EBF3",
    "accent": "#5B52E5",
    "accent_hover": "#6C63FF",
    "text": "#1A1A22",
    "muted": "#5C5F6A",
    "danger": "#C0392B",
    "danger_hover": "#E74C3C",
    "success": "#27AE60",
    "border": "#D7DAE4",
    "input_bg": "#FFFFFF",
    "input_border": "#B9BDCC",
    "selection": "#E3E1FF",
}

_QSS = Template("""
QMainWindow, QDialog, QMenu, QMenuBar, QStatusBar, QTipLabel {
    background: $bg;
    color: $text;
}
QWidget { color: $text; background: transparent; font-size: 10pt; }
QToolTip { background: $panel; color: $text; border: 1px solid $border; }
QMenuBar::item:selected { background: $selection; border-radius: 6px; }
QMenu { border: 1px solid $border; }
QMenu::item { padding: 7px 24px; }
QMenu::item:selected { background: $selection; }
QMenu::separator { height: 1px; background: $border; margin: 6px 10px; }

QPushButton {
    background: $panel_light; color: $text; border: 1px solid $border;
    border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background: $selection; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $muted; }
QPushButton#primaryButton {
    background: $accent; color: #FFFFFF; border: none;
    border-radius: 8px; padding: 9px 18px; font-weight: 600;
}
QPushButton#primaryButton:hover { background: $accent_hover; }
QPushButton#primaryButton:disabled { background: $panel_light; color: $muted; }
QPushButton#dangerButton { background: $danger; color: #FFFFFF; border: none; }
QPushButton#dangerButton:hover { background: $danger_hover; }
QPushButton[flat="true"] { background: transparent; border: none; color: $accent; }
QPushButton[flat="true"]:hover { color: $accent_hover; }

QLineEdit, QPlainTextEdit, QTextEdit {
    background: $input_bg; color: $text; border: 1px solid $input_border;
    border-radius: 8px; padding: 8px 10px; selection-background-color: $accent;
}
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid $accent; }
QLineEdit:disabled, QPlainTextEdit:disabled { color: $muted; background: $panel_light; }
QLineEdit#searchEdit { border-radius: 20px; padding: 10px 16px; font-size: 10.5pt; }

QListWidget {
    background: $panel; border: 1px solid $border; border-radius: 12px;
    padding: 6px; outline: 0;
}
QListWidget::item { padding: 9px 12px; border-radius: 8px; }
QListWidget::item:hover { background: $panel_light; }
QListWidget::item:selected { background: $accent; color: #FFFFFF; }
QListWidget::item:disabled { color: $muted; background: transparent; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#card { background: $panel; border: 1px solid $border; border-radius: 12px; }

QGroupBox {
    background: $panel; border: 1px solid $border; border-radius: 12px;
    margin-top: 16px; padding: 14px 12px 12px 12px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }

QLabel { color: $text; }
QLabel[muted="true"] { color: $muted; }
QLabel[heading="true"] { font-size: 16pt; font-weight: 700; }
QLabel[danger="true"] { color: $danger; }
QLabel#statusBadge {
    color: $muted; background: $panel_light; border-radius: 6px; padding: 2px 8px;
}

QComboBox {
    background: $input_bg; border: 1px solid $input_border;
    border-radius: 8px; padding: 7px 10px;
}
QComboBox:hover { border: 1px solid $accent; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: $panel; border: 1px solid $border;
    selection-background-color: $accent; selection-color: #FFFFFF; outline: 0;
}

QSpinBox {
    background: $input_bg; border: 1px solid $input_border;
    border-radius: 8px; padding: 6px 8px;
}
QSpinBox:focus { border: 1px solid $accent; }

QCheckBox, QRadioButton { spacing: 8px; padding: 2px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    background: $input_bg; border: 1px solid $input_border;
}
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: $accent; border: 1px solid $accent;
}

QProgressBar {
    background: $panel_light; border: none; border-radius: 5px;
    max-height: 10px; min-height: 10px;
}
QProgressBar::chunk { border-radius: 5px; background: $success; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 30px; }

QStatusBar { color: $muted; border-top: 1px solid $border; }
QSplitter::handle { background: $border; width: 1px; }
""")


def palette_for(theme: str) -> dict:
    return LIGHT if theme == "light" else DARK


def build_stylesheet(theme: str) -> str:
    return _QSS.substitute(palette_for(theme))


def load_logo_pixmap(size: int = 64) -> QPixmap | None:
    """Return the b.png logo scaled to fit `size`, or None if unavailable."""
    image = QImage(str(LOGO_PATH))
    if image.isNull():
        return None
    pixmap = QPixmap.fromImage(image)
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def create_app_icon() -> QIcon:
    logo = load_logo_pixmap(256)
    if logo is not None:
        return QIcon(logo)

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#6C63FF")))
    painter.drawRoundedRect(QRectF(6, 4, 52, 56), 15, 15)

    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.drawRoundedRect(QRectF(21, 30, 22, 17), 4, 4)
    shackle_pen = QPen(QColor("#FFFFFF"))
    shackle_pen.setWidthF(4.0)
    shackle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(shackle_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(25.5, 18, 13, 15), 0, 180 * 16)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#6C63FF")))
    painter.drawEllipse(QRectF(30, 35, 4, 4))
    painter.drawRect(QRectF(31.25, 38, 1.5, 5))
    painter.end()
    return QIcon(pixmap)
