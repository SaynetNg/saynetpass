"""Main dashboard: sidebar, search, entry cards, lock, backup, shortcuts."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.clipboard import Clipboard
from app.database import DatabaseError
from app.models import Entry, Vault, VaultError
from app.validators import sanitize_url

from .add_entry_dialog import AddEntryDialog
from .edit_entry_dialog import EditEntryDialog
from .password_generator_dialog import PasswordGeneratorDialog
from .settings_window import SettingsWindow
from .styles import load_logo_pixmap
from .theme import set_app_theme
from .unlock_window import UnlockWindow

_MASKED = "••••••••••••••"

_ACTIVITY_EVENTS = (
    QEvent.Type.KeyPress,
    QEvent.Type.MouseButtonPress,
    QEvent.Type.Wheel,
)


class EntryCard(QFrame):
    copy_requested = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    favorite_requested = Signal(int)
    site_requested = Signal(int)

    def __init__(self, entry: Entry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._revealed = False
        self.setObjectName("card")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(entry.title or "Untitled")
        title.setStyleSheet("font-size: 11pt; font-weight: 600;")
        star = QPushButton("★ Favorite" if entry.favorite else "☆ Favorite")
        star.setProperty("flat", True)
        star.setToolTip("Toggle favorite")
        star.clicked.connect(lambda: self.favorite_requested.emit(entry.id))
        header.addWidget(title, 1)
        header.addWidget(star)
        root.addLayout(header)

        detail = QHBoxLayout()
        preview = QLabel(entry.preview())
        preview.setProperty("muted", True)
        detail.addWidget(preview, 1)
        root.addLayout(detail)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        if not entry.is_note:
            self._password_label = QLabel(_MASKED)
            eye = QPushButton("👁")
            eye.setProperty("flat", True)
            eye.setToolTip("Show / hide password")
            eye.setAccessibleName("Show password")
            eye.clicked.connect(self._toggle_reveal)
            actions.addWidget(self._password_label)
            actions.addWidget(eye)
        actions.addStretch(1)

        copy_btn = QPushButton("Copy note" if entry.is_note else "Copy password")
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(entry.id))
        actions.addWidget(copy_btn)
        if sanitize_url(entry.website):
            site_btn = QPushButton("Open website")
            site_btn.setProperty("flat", True)
            site_btn.clicked.connect(lambda: self.site_requested.emit(entry.id))
            actions.addWidget(site_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(entry.id))
        actions.addWidget(edit_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("color: #E74C3C; border-color: #E74C3C;")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(entry.id))
        actions.addWidget(delete_btn)
        root.addLayout(actions)

    def _toggle_reveal(self) -> None:
        self._revealed = not self._revealed
        self._password_label.setText(
            self._entry.password if self._revealed else _MASKED
        )

    def clear_text(self) -> None:
        if hasattr(self, "_password_label"):
            self._password_label.setText("")
        for child in self.findChildren(QLabel):
            child.setText("")


class MainWindow(QMainWindow):
    def __init__(
        self,
        auth,
        settings: config.Settings,
        key: bytes,
        on_return_to_welcome,
    ) -> None:
        super().__init__()
        self._auth = auth
        self._settings = settings
        self._on_return_to_welcome = on_return_to_welcome
        self._clipboard = Clipboard(settings.clipboard_timeout_seconds)
        self._locking = False
        try:
            self.vault = Vault(auth.db, key)
        except (VaultError, DatabaseError) as exc:
            raise VaultError(str(exc))

        self.setWindowTitle(f"{config.APP_NAME}")
        self.resize(1080, 680)

        self._build_menus()
        self._build_ui()
        self._connect_shortcuts()

        self._lock_timer = QTimer(self)
        self._lock_timer.setSingleShot(True)
        self._lock_timer.timeout.connect(lambda: self._lock(due_to_inactivity=True))
        self._arm_autolock()
        QApplication.instance().installEventFilter(self)

        self._refresh()

    # ------------------------------------------------------------------ UI
    def _build_menus(self) -> None:
        menubar = self.menuBar()
        vault_menu = menubar.addMenu("&Vault")
        new_action = QAction("&New Entry", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._add_entry)
        vault_menu.addAction(new_action)
        backup_action = QAction("Create Encrypted &Backup…", self)
        backup_action.triggered.connect(self._backup)
        vault_menu.addAction(backup_action)
        restore_action = QAction("&Restore Encrypted Backup…", self)
        restore_action.triggered.connect(self._restore)
        vault_menu.addAction(restore_action)
        vault_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(QApplication.instance().closeAllWindows)
        vault_menu.addAction(quit_action)

        tools_menu = menubar.addMenu("&Tools")
        generator_action = QAction("Password &Generator", self)
        generator_action.setShortcut(QKeySequence("Ctrl+G"))
        generator_action.triggered.connect(
            lambda: PasswordGeneratorDialog(self, settings=self._settings, allow_use=False).exec()
        )
        tools_menu.addAction(generator_action)
        settings_action = QAction("&Settings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top_bar = QWidget()
        bar = QHBoxLayout(top_bar)
        bar.setContentsMargins(18, 12, 18, 8)
        logo = QLabel()
        logo_pixmap = load_logo_pixmap(28)
        if logo_pixmap is not None:
            logo.setPixmap(logo_pixmap)
            logo.setFixedSize(28, 28)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar.addWidget(logo)
            bar.addSpacing(8)
        title = QLabel("saynet.ng")
        title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        bar.addWidget(title)
        bar.addStretch(1)
        add_btn = QPushButton("+ Add Password")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_entry)
        add_btn.setToolTip("Create a new encrypted entry (Ctrl+N)")
        self._lock_btn = QPushButton("🔒 Lock")
        self._lock_btn.clicked.connect(lambda: self._lock())
        self._lock_btn.setToolTip("Lock the vault (Ctrl+L)")
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedWidth(44)
        settings_btn.clicked.connect(self._open_settings)
        settings_btn.setToolTip("Settings")
        bar.addWidget(add_btn)
        bar.addWidget(self._lock_btn)
        bar.addWidget(settings_btn)
        outer.addWidget(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setContentsMargins(18, 4, 18, 14)

        self._sidebar = QListWidget()
        self._sidebar.setMinimumWidth(210)
        self._sidebar.setMaximumWidth(260)
        self._sidebar.currentItemChanged.connect(lambda *_: self._refresh(reset_scroll=False))
        splitter.addWidget(self._sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        header = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setObjectName("searchEdit")
        self._search.setPlaceholderText("Search passwords...")
        self._search.setClearButtonEnabled(True)
        self._search.setAccessibleName("Search passwords")
        self._search.textChanged.connect(lambda _: self._refresh(reset_scroll=False))
        gen_btn = QPushButton("🎲 Generator")
        gen_btn.clicked.connect(
            lambda: PasswordGeneratorDialog(self, settings=self._settings, allow_use=False).exec()
        )
        self._count_label = QLabel("")
        self._count_label.setObjectName("statusBadge")
        header.addWidget(self._search, 1)
        header.addWidget(gen_btn)
        header.addWidget(self._count_label)
        content_layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(2, 2, 10, 2)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch(1)
        self._scroll.setWidget(self._cards_container)
        content_layout.addWidget(self._scroll, 1)

        splitter.addWidget(content)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, 1)

        self.statusBar().showMessage("Vault unlocked.", 4000)

    def _connect_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._search.setFocus)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=lambda: self._lock())

    # ------------------------------------------------------------- sidebar
    def _rebuild_sidebar(self) -> None:
        current = self._current_filter()
        entries = list(self.vault.entries)
        self._sidebar.blockSignals(True)
        self._sidebar.clear()

        def add_item(label: str, mode: str, value: str | None = None):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (mode, value))
            item.setData(Qt.ItemDataRole.AccessibleTextRole, label)
            self._sidebar.addItem(item)
            return item

        add_item(f"All Items  ({len(entries)})", "all")
        add_item(
            f"★ Favorites  ({sum(1 for e in entries if e.favorite)})", "fav"
        )
        notes_count = sum(1 for e in entries if e.is_note)
        add_item(f"📝 Secure Notes  ({notes_count})", "notes")

        header = QListWidgetItem("CATEGORIES")
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        self._sidebar.addItem(header)
        for category in self.vault.categories_present():
            count = sum(1 for e in entries if e.category == category)
            add_item(f"{category}  ({count})", "cat", category)

        row = 0
        for i in range(self._sidebar.count()):
            item = self._sidebar.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == current:
                row = i
                break
        self._sidebar.setCurrentRow(row)
        self._sidebar.blockSignals(False)

    def _current_filter(self):
        item = self._sidebar.currentItem()
        if item is None:
            return ("all", None)
        return item.data(Qt.ItemDataRole.UserRole) or ("all", None)

    def _entry_by_card_id(self, entry_id: int) -> Entry | None:
        return self.vault.by_id(entry_id)

    # ------------------------------------------------------------ refresh
    def _clear_cards(self) -> None:
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh(self, reset_scroll: bool = True) -> None:
        mode, value = self._current_filter()
        self._rebuild_sidebar()
        mode, value = self._current_filter()

        results = self.vault.search(self._search.text())
        if mode == "fav":
            results = [e for e in results if e.favorite]
        elif mode == "notes":
            results = [e for e in results if e.is_note]
        elif mode == "cat":
            results = [e for e in results if e.category == value]
        results.sort(key=lambda e: (e.favorite, e.created_at), reverse=True)

        self._clear_cards()
        for entry in results:
            card = EntryCard(entry, self)
            card.copy_requested.connect(self._copy_entry)
            card.edit_requested.connect(self._edit_entry)
            card.delete_requested.connect(self._delete_entry)
            card.favorite_requested.connect(self._toggle_favorite)
            card.site_requested.connect(self._open_website)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        if not results:
            empty = QLabel(
                "No entries yet — click “+ Add Password”."
                if not mode or mode == "all"
                else "No entries match this view."
            )
            empty.setProperty("muted", True)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, empty)

        self._count_label.setText(f"{len(results)} / {len(self.vault.entries)} items")
        if reset_scroll:
            self._scroll.verticalScrollBar().setValue(0)

    # ------------------------------------------------------------- actions
    def _add_entry(self) -> None:
        dialog = AddEntryDialog(self.vault.categories_present(), self, settings=self._settings)
        if not dialog.exec() or not dialog.data:
            return
        data = dialog.data
        try:
            self.vault.create_entry(
                data["title"],
                kind=data["kind"],
                username=data["username"],
                password=data["password"],
                website=data["website"],
                category=data["category"],
                notes=data["notes"],
                favorite=data["favorite"],
            )
        except (VaultError, DatabaseError):
            QMessageBox.warning(
                self, config.APP_NAME, "Unable to save password.\n\nPlease try again."
            )
            return
        self._refresh()
        self.statusBar().showMessage("Password saved.", 4000)

    def _edit_entry(self, entry_id: int) -> None:
        entry = self._entry_by_card_id(entry_id)
        if entry is None:
            return
        dialog = EditEntryDialog(
            self.vault.categories_present(), entry, self, settings=self._settings
        )
        if not dialog.exec() or not dialog.data:
            return
        try:
            self.vault.update_entry(entry, **dialog.data)
        except (VaultError, DatabaseError):
            QMessageBox.warning(
                self, config.APP_NAME, "Unable to save changes.\n\nPlease try again."
            )
            return
        self._refresh()
        self.statusBar().showMessage("Entry updated.", 4000)

    def _delete_entry(self, entry_id: int) -> None:
        entry = self._entry_by_card_id(entry_id)
        if entry is None:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Delete Password?")
        box.setText(f"Are you sure you want to delete:\n\n{entry.title}")
        box.setInformativeText("This action cannot be undone.")
        delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(box.buttons()[1])
        box.exec()
        if box.clickedButton() is not delete_btn:
            return
        try:
            self.vault.delete_entry(entry_id)
        except (VaultError, DatabaseError):
            QMessageBox.warning(self, config.APP_NAME, "Unable to delete the entry.")
            return
        self._refresh()
        self.statusBar().showMessage("Password deleted.", 4000)

    def _toggle_favorite(self, entry_id: int) -> None:
        entry = self._entry_by_card_id(entry_id)
        if entry is None:
            return
        try:
            self.vault.set_favorite(entry, not entry.favorite)
        except (VaultError, DatabaseError):
            QMessageBox.warning(self, config.APP_NAME, "Unable to update the entry.")
            return
        self._refresh()

    def _copy_entry(self, entry_id: int) -> None:
        entry = self._entry_by_card_id(entry_id)
        if entry is None:
            return
        text = entry.notes if entry.is_note else entry.password
        if not text:
            self.statusBar().showMessage("Nothing to copy.", 3000)
            return
        if self._clipboard.copy_secret(text):
            self.statusBar().showMessage("Password copied to clipboard.", 5000)
        else:
            QMessageBox.warning(self, config.APP_NAME, "Clipboard is unavailable.")

    def _open_website(self, entry_id: int) -> None:
        entry = self._entry_by_card_id(entry_id)
        if entry is None:
            return
        url = sanitize_url(entry.website)
        if not url:
            self.statusBar().showMessage("The stored link is not a valid URL.", 4000)
            return
        QDesktopServices.openUrl(QUrl(url))

    # --------------------------------------------------------------- lock
    def _arm_autolock(self) -> None:
        minutes = int(self._settings.auto_lock_minutes or 0)
        if minutes > 0:
            self._lock_timer.setInterval(minutes * 60_000)
            self._lock_timer.start()
        else:
            self._lock_timer.stop()

    def eventFilter(self, obj, event) -> bool:
        if (
            event.type() in _ACTIVITY_EVENTS
            and not self._locking
            and self._settings.auto_lock_minutes > 0
            and self.vault is not None
            and not self.vault.is_locked
        ):
            self._lock_timer.start()
        return super().eventFilter(obj, event)

    def _lock(self, due_to_inactivity: bool = False) -> None:
        if self._locking or self.vault.is_locked:
            return
        self._locking = True
        self._lock_timer.stop()
        QApplication.instance().removeEventFilter(self)
        for card in self.findChildren(EntryCard):
            card.clear_text()
        self.vault.lock()
        self._clear_cards()
        self._rebuild_sidebar()
        note = "Vault locked due to inactivity." if due_to_inactivity else None
        if due_to_inactivity:
            self.statusBar().showMessage(note, 6000)
        dialog = UnlockWindow(self._auth, self, note=note)
        accepted = dialog.exec()
        dialog.deleteLater()
        if accepted and dialog.session_key:
            try:
                self.vault = Vault(self._auth.db, dialog.session_key)
            except (VaultError, DatabaseError):
                QMessageBox.critical(
                    self, config.APP_NAME, "Unable to open the vault database."
                )
                self._locking = False
                self._return_to_welcome()
                return
            self._locking = False
            self._arm_autolock()
            QApplication.instance().installEventFilter(self)
            self._refresh()
            return
        self._locking = False
        self._clipboard.clear_expired_secret()
        self._return_to_welcome()

    def _return_to_welcome(self) -> None:
        self.hide()
        self._on_return_to_welcome()

    # ------------------------------------------------------- vault health
    def _backup(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = str(config.DATA_DIR / f"vault-backup-{stamp}.db")
        destination, _ = QFileDialog.getSaveFileName(
            self, "Create Encrypted Backup", default_name, "Encrypted vault (*.db)"
        )
        if not destination:
            return
        try:
            self._auth.db.backup_to(destination)
        except DatabaseError as exc:
            QMessageBox.warning(self, config.APP_NAME, str(exc))
            return
        QMessageBox.information(
            self,
            config.APP_NAME,
            "Backup created successfully.\n\nThe backup file is encrypted with "
            "the same vault encryption and is only usable with your master "
            "password.",
        )

    def _restore(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Restore Encrypted Vault")
        box.setText(
            "Restoring replaces the current encrypted vault with the selected "
            "backup.\n\nYou will need the master password of the backup.\n\n"
            "Continue?"
        )
        yes = box.addButton("Restore", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return
        source, _ = QFileDialog.getOpenFileName(
            self, "Restore Encrypted Backup", str(config.DATA_DIR), "Encrypted vault (*.db)"
        )
        if not source:
            return
        self.vault.lock()
        self._clear_cards()
        try:
            self._auth.db.restore_from(source)
        except DatabaseError as exc:
            QMessageBox.warning(self, config.APP_NAME, str(exc))
            dialog = UnlockWindow(self._auth, self, note="Vault restored. Unlock again.")
            if dialog.exec() and dialog.session_key:
                try:
                    self.vault = Vault(self._auth.db, dialog.session_key)
                except (VaultError, DatabaseError):
                    self._return_to_welcome()
            return
        self._auth.reset_backoff()
        dialog = UnlockWindow(
            self._auth,
            self,
            note="Vault restored from backup. Unlock it with the backup's master password.",
        )
        if dialog.exec() and dialog.session_key:
            try:
                self.vault = Vault(self._auth.db, dialog.session_key)
            except (VaultError, DatabaseError):
                QMessageBox.critical(self, config.APP_NAME, "Unable to open the vault.")
                self._return_to_welcome()
                return
            self._arm_autolock()
            QApplication.instance().installEventFilter(self)
            self._refresh()
            self.statusBar().showMessage("Vault restored.", 5000)
        else:
            self._return_to_welcome()

    def _open_settings(self) -> None:
        metadata = self._auth.db.get_metadata()
        dialog = SettingsWindow(self._settings, metadata, str(self._auth.db.path), self)
        if not dialog.exec():
            return
        set_app_theme(
            QApplication.instance(),
            self._settings.theme,
        )
        self._clipboard.set_timeout(self._settings.clipboard_timeout_seconds)
        self._arm_autolock()
        self.statusBar().showMessage("Settings saved.", 4000)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            f"About {config.APP_NAME}",
            f"<b>{config.APP_NAME} {config.APP_VERSION}</b><br><br>"
            "Built for the community — a free, offline password manager.<br>"
            "Developed for the community and usable across different "
            "platforms: Windows, Linux (including Raspberry Pi devices), "
            "macOS, and any system that supports Python.<br><br>"
            "Keys are derived with Argon2id; vault data is encrypted with "
            "AES-256-GCM (unique random nonce per record).<br><br>"
            "Security note: a running, unlocked vault can be affected by "
            "malware, keyloggers, or memory inspection — keep your device "
            "trusted.",
        )

    # -------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        self._lock_timer.stop()
        if self.vault is not None and not self.vault.is_locked:
            self.vault.lock()
        super().closeEvent(event)
