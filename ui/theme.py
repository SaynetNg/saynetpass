"""Theme application: resolve light/dark/system and apply QSS + palette app-wide."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from .styles import build_stylesheet, palette_for


def _detect_system_theme(app) -> str:
    hints = app.styleHints()
    if hasattr(hints, "colorScheme"):
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
            return "light"

    if sys.platform == "win32":
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value else "dark"
        except Exception:
            return "light"

    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, timeout=2, check=True,
            )
            return "dark"
        except Exception:
            return "light"

    for schema, prop, dark_value in (
        ("org.gnome.desktop.interface", "color-scheme", "prefer-dark"),
        ("org.gnome.desktop.interface", "gtk-theme", "dark"),
    ):
        try:
            out = subprocess.run(
                ["gsettings", "get", schema, prop],
                capture_output=True, text=True, timeout=2,
            ).stdout
            if dark_value in out.lower():
                return "dark"
        except Exception:
            continue
    return "light"


def build_palette(theme: str) -> QPalette:
    c = palette_for(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(c["input_bg"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["panel"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(c["panel_light"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["muted"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(c["accent"]))
    disabled = QColor(c["muted"])
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def resolve_app_theme(app, theme: str) -> str:
    if theme == "system":
        return _detect_system_theme(app)
    return "light" if theme == "light" else "dark"


def set_app_theme(app, theme: str) -> str:
    resolved = resolve_app_theme(app, theme)
    app.setPalette(build_palette(resolved))
    app.setStyleSheet(build_stylesheet(resolved))
    return resolved
