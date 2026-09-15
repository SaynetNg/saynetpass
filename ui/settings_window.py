"""Settings dialog: security, appearance, generator defaults, vault info."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QApplication

from app.config import AUTO_LOCK_CHOICES_MINUTES, Settings, save_settings

from .theme import set_app_theme
from .utils_scroll import wrap_scrollable

_AUTO_LOCK_LABELS = {0: "Never", 1: "1 minute", 5: "5 minutes",
                     10: "10 minutes", 30: "30 minutes"}


class SettingsWindow(QDialog):
    """Mutates the passed `Settings` object in place and persists it."""

    def __init__(
        self,
        settings: Settings,
        vault_metadata: dict | None,
        vault_path: str | sqlite3.Connection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._initial_theme = settings.theme
        self.setWindowTitle("Settings")
        self.setFixedWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(14)

        title = QLabel("Settings")
        title.setProperty("heading", True)
        body_layout.addWidget(title)

        # -- Security -----------------------------------------------------
        security = QGroupBox("Security")
        sec_form = QFormLayout(security)
        sec_form.setSpacing(10)
        self._auto_lock = QComboBox()
        for minutes in AUTO_LOCK_CHOICES_MINUTES:
            self._auto_lock.addItem(_AUTO_LOCK_LABELS.get(minutes, f"{minutes} minutes"), minutes)
        index = self._auto_lock.findData(settings.auto_lock_minutes)
        self._auto_lock.setCurrentIndex(max(0, index))
        sec_form.addRow("Auto-lock timeout:", self._auto_lock)

        self._clipboard_timeout = QSpinBox()
        self._clipboard_timeout.setRange(5, 300)
        self._clipboard_timeout.setSuffix(" seconds")
        self._clipboard_timeout.setValue(settings.clipboard_timeout_seconds)
        sec_form.addRow("Password clipboard timeout:", self._clipboard_timeout)
        body_layout.addWidget(security)

        # -- Appearance ---------------------------------------------------
        appearance = QGroupBox("Appearance")
        app_row = QHBoxLayout(appearance)
        app_row.setSpacing(18)
        self._theme_buttons: dict[str, QRadioButton] = {}
        for key, caption in (("light", "Light"), ("dark", "Dark"), ("system", "System")):
            button = QRadioButton(caption)
            button.setChecked(settings.theme == key)
            button.toggled.connect(lambda on, k=key: on and self._preview_theme(k))
            app_row.addWidget(button)
            self._theme_buttons[key] = button
        app_row.addStretch(1)
        body_layout.addWidget(appearance)

        # -- Generator defaults --------------------------------------------
        generator = QGroupBox("Password Generator")
        gen_form = QFormLayout(generator)
        gen_form.setSpacing(10)
        self._gen_length = QSpinBox()
        self._gen_length.setRange(8, 64)
        self._gen_length.setValue(settings.generator_length)
        gen_form.addRow("Default password length:", self._gen_length)

        self._gen_symbols = QCheckBox("Include symbols")
        self._gen_symbols.setChecked(settings.generator_symbols)
        gen_form.addRow("", self._gen_symbols)
        self._gen_digits = QCheckBox("Include numbers")
        self._gen_digits.setChecked(settings.generator_digits)
        gen_form.addRow("", self._gen_digits)
        self._gen_upper = QCheckBox("Include uppercase")
        self._gen_upper.setChecked(settings.generator_uppercase)
        gen_form.addRow("", self._gen_upper)
        self._gen_lower = QCheckBox("Include lowercase")
        self._gen_lower.setChecked(settings.generator_lowercase)
        gen_form.addRow("", self._gen_lower)
        self._gen_ambiguous = QCheckBox("Exclude ambiguous characters")
        self._gen_ambiguous.setChecked(settings.generator_exclude_ambiguous)
        gen_form.addRow("", self._gen_ambiguous)
        body_layout.addWidget(generator)

        # -- Vault (metadata only — never any key material) ----------------
        vault_box = QGroupBox("Vault")
        vault_form = QFormLayout(vault_box)
        vault_form.setSpacing(10)
        path_text = str(vault_path) if vault_path is not None else "-"
        created = "-"
        version = "-"
        if vault_metadata:
            created = str(vault_metadata.get("created_at", "-"))
            version = str(vault_metadata.get("version", "-"))
        loc = QLabel(path_text)
        loc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        loc.setWordWrap(True)
        vault_form.addRow("Vault location:", loc)
        vault_form.addRow("Database version:", QLabel(version))
        vault_form.addRow("Created:", QLabel(created))
        body_layout.addWidget(vault_box)

        note = QLabel(
            "Encryption keys are only ever held in memory while the vault is "
            "unlocked and are never displayed or stored."
        )
        note.setProperty("muted", True)
        note.setWordWrap(True)
        body_layout.addWidget(note)

        root.addWidget(wrap_scrollable(body))

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _save(self) -> None:
        s = self._settings
        s.auto_lock_minutes = int(self._auto_lock.currentData())
        s.clipboard_timeout_seconds = int(self._clipboard_timeout.value())
        s.generator_length = int(self._gen_length.value())
        s.generator_symbols = self._gen_symbols.isChecked()
        s.generator_digits = self._gen_digits.isChecked()
        s.generator_uppercase = self._gen_upper.isChecked()
        s.generator_lowercase = self._gen_lower.isChecked()
        s.generator_exclude_ambiguous = self._gen_ambiguous.isChecked()
        for key, button in self._theme_buttons.items():
            if button.isChecked():
                s.theme = key
        save_settings(s)
        set_app_theme(QApplication.instance(), s.theme)
        self.accept()

    def _preview_theme(self, key: str) -> None:
        set_app_theme(QApplication.instance(), key)

    def reject(self) -> None:
        super().reject()
        set_app_theme(QApplication.instance(), self._initial_theme)
