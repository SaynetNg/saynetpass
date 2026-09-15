"""Clipboard with automatic, timed clearing of secrets."""

from __future__ import annotations

from . import config
from .utils import get_logger

log = get_logger("clipboard")

DEFAULT_CLEAR_SECONDS = 30


class Clipboard:
    """Copies secrets and clears them again unless the user copied something
    different in the meantime. Contents are never logged."""

    def __init__(self, clear_seconds: int = DEFAULT_CLEAR_SECONDS) -> None:
        self.clear_seconds = max(5, int(clear_seconds))
        self._pending_secret: str | None = None

    @staticmethod
    def _toolkit_clipboard():
        from PySide6.QtWidgets import QApplication

        return QApplication.clipboard()

    def copy_secret(self, text: str) -> bool:
        if not text:
            return False
        clipboard = self._toolkit_clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        self._pending_secret = text
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(self.clear_seconds * 1000, self.clear_expired_secret)
        except Exception:
            log.error("Clipboard clear timer could not be scheduled.")
        return True

    def clear_expired_secret(self) -> None:
        secret, self._pending_secret = self._pending_secret, None
        if secret is None:
            return
        clipboard = self._toolkit_clipboard()
        if clipboard is None:
            return
        try:
            if clipboard.text() == secret:
                clipboard.clear()
                log.info("Clipboard secret cleared after timeout.")
        except Exception:
            log.error("Clipboard could not be cleared.")

    def set_timeout(self, seconds: int) -> None:
        self.clear_seconds = max(5, int(seconds))
