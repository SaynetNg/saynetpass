"""Create-vault dialog: master password setup with strength meter,
explicit acknowledgement, and strict no-storage guarantees."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.auth import AuthError
from app.config import MIN_MASTER_PASSWORD_LENGTH
from app.database import DatabaseError
from app.validators import passwords_match, validate_master_password
from .password_strength_widget import PasswordField, PasswordStrengthWidget
from .utils_scroll import wrap_scrollable


class SetupWindow(QDialog):
    def __init__(self, auth_manager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auth = auth_manager
        self.session_key: bytes | None = None

        self.setWindowTitle("Create New Vault")
        self.setFixedWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(14)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(14)

        title = QLabel("Create New Vault")
        title.setProperty("heading", True)
        subtitle = QLabel(
            "Choose one strong master password. It is never stored — it is used "
            "only to derive the encryption key for your local vault."
        )
        subtitle.setProperty("muted", True)
        subtitle.setWordWrap(True)
        body_layout.addWidget(title)
        body_layout.addWidget(subtitle)

        warning = QFrame()
        warning.setObjectName("card")
        warning_layout = QVBoxLayout(warning)
        warning_title = QLabel("IMPORTANT")
        warning_title.setProperty("danger", True)
        warning_text = QLabel(
            "Your master password cannot be recovered.\n"
            "If you forget it, your encrypted vault cannot be decrypted."
        )
        warning_text.setWordWrap(True)
        self._ack = QCheckBox("I Understand")
        warning_layout.addWidget(warning_title)
        warning_layout.addWidget(warning_text)
        warning_layout.addWidget(self._ack)
        body_layout.addWidget(warning)

        body_layout.addSpacing(4)
        master_label = QLabel("Master Password")
        self._password = PasswordField("At least "
            f"{MIN_MASTER_PASSWORD_LENGTH} characters")
        self._password.line_edit().setAccessibleName("Master password")
        body_layout.addWidget(master_label)
        body_layout.addWidget(self._password)

        confirm_label = QLabel("Confirm Master Password")
        self._confirm = PasswordField("Repeat the master password")
        self._confirm.line_edit().setAccessibleName("Confirm master password")
        body_layout.addWidget(confirm_label)
        body_layout.addWidget(self._confirm)

        strength_label = QLabel("Password Strength")
        strength_label.setProperty("muted", True)
        self._strength = PasswordStrengthWidget()
        body_layout.addWidget(strength_label)
        body_layout.addWidget(self._strength)

        self._hint = QLabel(
            "\nUse a long, unique passphrase. Avoid common words and personal "
            "information."
        )
        self._hint.setProperty("muted", True)
        self._hint.setWordWrap(True)
        body_layout.addWidget(self._hint)

        self._errors = QLabel()
        self._errors.setProperty("danger", True)
        self._errors.setWordWrap(True)
        self._errors.hide()
        body_layout.addWidget(self._errors)

        root.addWidget(wrap_scrollable(body))

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self._create_btn = QPushButton("Create Vault")
        self._create_btn.setObjectName("primaryButton")
        self._create_btn.setDefault(True)
        self._create_btn.setEnabled(False)
        self._create_btn.clicked.connect(self._create)
        buttons.addWidget(cancel)
        buttons.addWidget(self._create_btn)
        root.addLayout(buttons)

        for field in (self._password, self._confirm):
            edit = field.line_edit()
            edit.textChanged.connect(self._update)
            edit.returnPressed.connect(self._create)
        self._ack.stateChanged.connect(self._update)
        self._password.line_edit().setFocus()

    # ------------------------------------------------------------------
    def _policy_errors(self) -> list[str]:
        password = self._password.text()
        confirmation = self._confirm.text()
        errors = validate_master_password(password)
        if password and confirmation and not passwords_match(password, confirmation):
            errors.append("The passwords do not match.")
        return errors

    def _update(self) -> None:
        self._strength.set_password(self._password.text())
        errors = self._policy_errors()
        if errors:
            self._hint.setText(" ".join(f"• {e}" for e in errors))
        else:
            self._hint.setText("Password policy requirements met.")
        ready = bool(
            self._ack.isChecked() and self._password.text() and not errors
        )
        self._create_btn.setEnabled(ready)

    def _create(self) -> None:
        password = self._password.text()
        errors = self._policy_errors()
        if errors or not password:
            self._errors.setText("\n".join(errors) or "A master password is required.")
            self._errors.show()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QCoreApplication.processEvents()
        try:
            key = self._auth.create_vault(password)
        except (AuthError, DatabaseError) as exc:
            self._errors.setText(str(exc))
            self._errors.show()
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._password.clear()
        self._confirm.clear()
        self._errors.hide()
        self.session_key = key
        self.accept()
