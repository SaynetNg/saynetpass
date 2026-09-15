"""Standalone / reusable secure password generator dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.clipboard import Clipboard
from app.config import Settings
from app.password_generator import GeneratorConfigError, generate_password

from .password_strength_widget import PasswordStrengthWidget
from .utils_scroll import wrap_scrollable


class PasswordGeneratorDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings: Settings | None = None,
        allow_use: bool = True,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or Settings()
        self.selected_password: str | None = None
        self._clipboard = Clipboard(self._settings.clipboard_timeout_seconds)

        self.setWindowTitle("Password Generator")
        self.setFixedWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(12)

        title = QLabel("Password Generator")
        title.setProperty("heading", True)
        body_layout.addWidget(title)

        self._output = QLineEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11pt;"
        )
        self._output.setAccessibleName("Generated password")
        body_layout.addWidget(self._output)

        self._status = QLabel("")
        self._status.setProperty("muted", True)
        self._status.setWordWrap(True)
        body_layout.addWidget(self._status)

        self._strength = PasswordStrengthWidget()
        body_layout.addWidget(self._strength)

        row = QHBoxLayout()
        row.addWidget(QLabel("Password Length"))
        self._length = QSpinBox()
        self._length.setRange(8, 64)
        self._length.setValue(max(8, min(64, self._settings.generator_length)))
        self._length.setAccessibleName("Password length")
        row.addWidget(self._length)
        row.addStretch(1)
        body_layout.addLayout(row)

        self._upper = QCheckBox("Uppercase (A-Z)")
        self._lower = QCheckBox("Lowercase (a-z)")
        self._digits = QCheckBox("Numbers (0-9)")
        self._symbols = QCheckBox("Symbols (!@#$)")
        self._ambiguous = QCheckBox("Exclude ambiguous characters (l1IO0)")
        for box, value in (
            (self._upper, self._settings.generator_uppercase),
            (self._lower, self._settings.generator_lowercase),
            (self._digits, self._settings.generator_digits),
            (self._symbols, self._settings.generator_symbols),
            (self._ambiguous, self._settings.generator_exclude_ambiguous),
        ):
            box.setChecked(bool(value))
            box.toggled.connect(lambda _=False: self._generate())
            body_layout.addWidget(box)

        info = QLabel("Generated with the Python `secrets` CSPRNG.")
        info.setProperty("muted", True)
        body_layout.addWidget(info)

        root.addWidget(wrap_scrollable(body))

        action_row = QHBoxLayout()
        regenerate = QPushButton("Generate")
        regenerate.clicked.connect(self._generate)
        copy = QPushButton("Copy")
        copy.clicked.connect(self._copy)
        action_row.addWidget(regenerate)
        action_row.addWidget(copy)
        action_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        self._use_btn = QPushButton("Use Password")
        self._use_btn.setObjectName("primaryButton")
        self._use_btn.clicked.connect(self._use)
        self._use_btn.setVisible(allow_use)
        action_row.addWidget(close_btn)
        action_row.addWidget(self._use_btn)
        root.addLayout(action_row)

        self._generate()

    # ------------------------------------------------------------------
    def _generate(self) -> None:
        try:
            password = generate_password(
                self._length.value(),
                use_uppercase=self._upper.isChecked(),
                use_lowercase=self._lower.isChecked(),
                use_digits=self._digits.isChecked(),
                use_symbols=self._symbols.isChecked(),
                exclude_ambiguous=self._ambiguous.isChecked(),
            )
        except GeneratorConfigError as exc:
            self._output.clear()
            self._status.setText(str(exc))
            self._strength.set_password("")
            return
        self._output.setText(password)
        self._strength.set_password(password)
        self._status.setText("")

    def _copy(self) -> None:
        password = self._output.text()
        if password and self._clipboard.copy_secret(password):
            self._status.setText(
                f"Copied. Clipboard clears automatically after "
                f"{self._clipboard.clear_seconds} seconds."
            )

    def _use(self) -> None:
        password = self._output.text()
        if password:
            self.selected_password = password
            self._output.clear()
            self.accept()
