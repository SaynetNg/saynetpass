"""Shared add/edit entry dialog with validation, generator, and strength."""

from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DEFAULT_CATEGORIES
from app.models import KIND_LOGIN, KIND_NOTE, Entry
from app.validators import (
    sanitize_url,
    validate_category,
    validate_entry_title,
    validate_notes,
    validate_password_field,
    validate_username,
    validate_website,
)

from .password_generator_dialog import PasswordGeneratorDialog
from .password_strength_widget import PasswordField, PasswordStrengthWidget
from .utils_scroll import wrap_scrollable


def _field_block(caption: str, control: QWidget, muted: bool = True) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(caption)
    if muted:
        label.setProperty("muted", True)
    layout.addWidget(label)
    layout.addWidget(control)
    return wrapper


class EntryDialog(QDialog):
    """Editing dialog; subclasses give the add/edit semantics required by
    the design. `self.data` holds the validated field dict after accept()."""

    def __init__(
        self,
        categories: list[str],
        parent: QWidget | None = None,
        *,
        settings=None,
        entry: Entry | None = None,
    ) -> None:
        super().__init__(parent)
        self._entry = entry
        self._settings = settings
        self.data: dict | None = None

        self.setWindowTitle("Add Password" if entry is None else "Edit Entry")
        self.setFixedWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(12)

        self._kind_combo = QComboBox()
        self._kind_combo.addItems(["Login", "Secure note"])
        self._kind_combo.setAccessibleName("Entry type")
        self._kind_combo.currentIndexChanged.connect(self._update_kind)
        body_layout.addWidget(_field_block("Type", self._kind_combo))

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("e.g. GitHub")
        self._title_edit.setAccessibleName("Title")
        body_layout.addWidget(_field_block("Title *", self._title_edit))

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("user@example.com")
        self._username_edit.setAccessibleName("Username or email")
        self._username_block = _field_block("Username / Email", self._username_edit)
        body_layout.addWidget(self._username_block)

        self._password_field = PasswordField("Password")
        self._password_line = self._password_field.line_edit()
        self._password_line.setAccessibleName("Password")
        self._password_line.textChanged.connect(self._on_password_changed)
        generate_btn = QPushButton("Generate Password")
        generate_btn.setProperty("flat", True)
        generate_btn.clicked.connect(self._open_generator)
        pw_row = QHBoxLayout()
        pw_row.setContentsMargins(0, 0, 0, 0)
        pw_row.addWidget(self._password_field, 1)
        pw_row.addWidget(generate_btn)
        pw_widget = QWidget()
        pw_widget.setLayout(pw_row)
        self._password_block = _field_block("Password", pw_widget)
        body_layout.addWidget(self._password_block)

        self._strength = PasswordStrengthWidget()
        body_layout.addWidget(self._strength)

        self._website_edit = QLineEdit()
        self._website_edit.setPlaceholderText("https://github.com")
        self._website_edit.setAccessibleName("Website URL")
        self._website_block = _field_block("Website", self._website_edit)
        body_layout.addWidget(self._website_block)

        self._category_combo = QComboBox()
        self._category_combo.setEditable(True)
        merged = list(DEFAULT_CATEGORIES)
        merged.extend(c for c in categories if c and c not in merged)
        self._category_combo.addItems(merged)
        self._category_combo.setAccessibleName("Category")
        body_layout.addWidget(_field_block("Category", self._category_combo))

        self._favorite_check = QCheckBox("★  Favorite")
        self._favorite_check.setAccessibleName("Favorite")
        body_layout.addWidget(self._favorite_check)

        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText("Notes (encrypted with the entry)…")
        self._notes_edit.setFixedHeight(96)
        self._notes_edit.setAccessibleName("Notes")
        body_layout.addWidget(_field_block("Notes", self._notes_edit))

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
        save = QPushButton("Save")
        save.setObjectName("primaryButton")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save)

        if entry is not None:
            self._prefill(entry)
        self._update_kind()
        self._title_edit.setFocus()

    # ------------------------------------------------------------------
    def _prefill(self, entry: Entry) -> None:
        self._kind_combo.setCurrentIndex(1 if entry.is_note else 0)
        self._kind_combo.setEnabled(False)
        self._title_edit.setText(entry.title)
        self._username_edit.setText(entry.username)
        self._password_line.setText(entry.password)
        self._website_edit.setText(entry.website)
        self._category_combo.setCurrentText(entry.category or "Personal")
        self._favorite_check.setChecked(entry.favorite)
        self._notes_edit.setPlainText(entry.notes)

    def _update_kind(self) -> None:
        note = self._kind_combo.currentIndex() == 1
        self._username_block.setVisible(not note)
        self._password_block.setVisible(not note)
        self._strength.setVisible(not note)
        self._website_block.setVisible(not note)

    def _on_password_changed(self, text: str) -> None:
        self._strength.set_password(text)

    def _open_generator(self) -> None:
        dialog = PasswordGeneratorDialog(self, settings=self._settings, allow_use=True)
        if dialog.exec() and dialog.selected_password:
            self._password_line.setText(dialog.selected_password)

    # ------------------------------------------------------------------
    def _collect(self) -> dict | None:
        note = self._kind_combo.currentIndex() == 1
        kind = KIND_NOTE if note else KIND_LOGIN
        title = self._title_edit.text().strip()
        username = self._username_edit.text()
        password = self._password_line.text()
        website_raw = self._website_edit.text().strip()
        category = self._category_combo.currentText().strip() or "Personal"
        notes = self._notes_edit.toPlainText()
        favorite = self._favorite_check.isChecked()

        errors = validate_entry_title(title)
        errors += validate_category(category)
        if not note:
            errors += validate_username(username)
            errors += validate_password_field(password)
            errors += validate_website(website_raw)
        errors += validate_notes(notes)

        website = "" if note else (sanitize_url(website_raw) or "")
        if website_raw and not website and not note:
            if not any("website" in err.lower() for err in errors):
                errors.append("The website must be a valid http(s) URL.")
        if note:
            username = password = website = ""

        if errors:
            self._errors.setText("\n".join(errors))
            self._errors.show()
            return None
        self._errors.hide()
        return {
            "kind": kind,
            "title": title,
            "username": username,
            "password": password,
            "website": website,
            "category": category,
            "notes": notes,
            "favorite": favorite,
        }

    def _save(self) -> None:
        data = self._collect()
        if data is None:
            return
        self.data = data
        self._password_line.clear()
        self._errors.hide()
        self.accept()


class AddEntryDialog(EntryDialog):
    """Empty form for creating a new encrypted entry."""

    def __init__(self, categories: list[str], parent: QWidget | None = None, *, settings=None) -> None:
        super().__init__(categories, parent, settings=settings, entry=None)
