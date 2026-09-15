"""Unlock dialog with correct/incorrect outcome and brute-force backoff."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.auth import (
    AuthError,
    TooManyAttemptsError,
    VaultNotFoundError,
    WrongMasterPasswordError,
)

from .utils_scroll import wrap_scrollable

WRONG_PASSWORD_MESSAGE = (
    "Unable to unlock the vault.\n\nThe master password may be incorrect."
)


class UnlockWindow(QDialog):
    def __init__(
        self,
        auth_manager,
        parent: QWidget | None = None,
        note: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._auth = auth_manager
        self.session_key: bytes | None = None

        self.setWindowTitle("Unlock Your Vault")
        self.setFixedWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 26)
        root.setSpacing(12)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(12)

        title = QLabel("Unlock Your Vault")
        title.setProperty("heading", True)
        subtitle = QLabel("Enter your master password to decrypt your vault.")
        subtitle.setProperty("muted", True)
        body_layout.addWidget(title)
        body_layout.addWidget(subtitle)

        if note:
            note_label = QLabel(note)
            note_label.setWordWrap(True)
            note_label.setStyleSheet("font-weight: 600;")
            body_layout.addWidget(note_label)

        from .password_strength_widget import PasswordField

        self._password = PasswordField("Master Password")
        self._password.line_edit().setAccessibleName("Master password")
        self._password.line_edit().setPlaceholderText("Master Password")
        self._password.line_edit().returnPressed.connect(self._try_unlock)
        body_layout.addWidget(self._password)

        self._error = QLabel()
        self._error.setProperty("danger", True)
        self._error.setWordWrap(True)
        self._error.hide()
        body_layout.addWidget(self._error)

        hint = QLabel(
            "Forgot your password? Your master password cannot be recovered."
        )
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        body_layout.addWidget(hint)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)

        root.addWidget(wrap_scrollable(body))

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Back")
        cancel.clicked.connect(self.reject)
        self._unlock_btn = QPushButton("Unlock")
        self._unlock_btn.setObjectName("primaryButton")
        self._unlock_btn.setDefault(True)
        self._unlock_btn.clicked.connect(self._try_unlock)
        buttons.addWidget(cancel)
        buttons.addWidget(self._unlock_btn)
        root.addLayout(buttons)

        self._password.line_edit().setFocus()

    # ------------------------------------------------------------------
    def _show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()

    def _try_unlock(self) -> None:
        password = self._password.text()
        if not password:
            self._show_error("Please enter your master password.")
            return
        remaining = self._auth.seconds_until_next_attempt()
        if remaining > 0:
            self._begin_countdown()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QCoreApplication.processEvents()
        try:
            key = self._auth.unlock(password)
        except WrongMasterPasswordError:
            self._password.clear()
            self._show_error(WRONG_PASSWORD_MESSAGE)
            self._password.line_edit().setFocus()
            return
        except TooManyAttemptsError as exc:
            self._password.clear()
            self._begin_countdown(exc.wait_seconds)
            return
        except VaultNotFoundError:
            self._show_error("Unable to open the vault database.")
            return
        except AuthError:
            self._show_error("Unable to unlock the vault. Please try again.")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._password.clear()
        self._error.hide()
        self.session_key = key
        self.accept()

    def _begin_countdown(self, seconds: float | None = None) -> None:
        remaining = seconds if seconds is not None else self._auth.seconds_until_next_attempt()
        self._unlock_btn.setEnabled(False)
        self._show_error(
            f"Too many failed attempts. Try again in {int(remaining) + 1} second(s)."
        )
        self._countdown_timer.start()

    def _tick_countdown(self) -> None:
        remaining = self._auth.seconds_until_next_attempt()
        if remaining <= 0:
            self._countdown_timer.stop()
            self._unlock_btn.setEnabled(True)
            self._error.setText("Check the password carefully and try again.")
            self._password.line_edit().setFocus()
            return
        self._error.setText(f"Too many failed attempts. Try again in {int(remaining) + 1} second(s).")
