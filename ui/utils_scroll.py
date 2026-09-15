"""Shared helper: wrap dialog/page content in a vertical scroll area so it
stays fully reachable on short screens."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QScrollArea, QWidget


def wrap_scrollable(content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidget(content)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    screen = QGuiApplication.primaryScreen()
    available = screen.availableGeometry().height() if screen else 1080
    cap = max(available - 200, 360)
    hint = content.sizeHint().height()
    scroll.setMinimumHeight(min(hint, cap))
    scroll.setMaximumHeight(cap)
    return scroll
