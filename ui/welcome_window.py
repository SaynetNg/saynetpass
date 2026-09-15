"""First-launch / welcome screen and top-level navigation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.auth import AuthManager
from app.config import APP_NAME, APP_VERSION, VAULT_DB_PATH, load_settings
from app.database import DatabaseError

from .setup_window import SetupWindow
from .unlock_window import UnlockWindow


class WelcomeWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = load_settings()
        self._start_error: str | None = None
        self._auth = None
        try:
            self._auth = AuthManager()
        except DatabaseError as exc:
            self._start_error = str(exc)
        self._main = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 500)
        self.resize(560, 520)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QWidget()
        card.setObjectName("card")
        card.setFixedWidth(440)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(36, 40, 36, 32)
        inner.setSpacing(10)
        holder_layout.addWidget(card)

        scroll = QScrollArea()
        scroll.setWidget(holder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        logo = QLabel()
        logo.setPixmap(QApplication.windowIcon().pixmap(72, 72))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(APP_NAME)
        name.setProperty("heading", True)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline = QLabel("Your passwords.\nSecure. Private. Offline.")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setProperty("muted", True)
        inner.addWidget(logo)
        inner.addWidget(name)
        inner.addWidget(tagline)
        inner.addSpacing(18)

        self._create_btn = QPushButton("Create New Vault")
        self._create_btn.setObjectName("primaryButton")
        self._create_btn.setMinimumHeight(44)
        self._create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._create_btn.clicked.connect(self._create_vault)
        self._unlock_btn = QPushButton("Unlock Existing Vault")
        self._unlock_btn.setMinimumHeight(44)
        self._unlock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unlock_btn.clicked.connect(self._unlock_vault)
        inner.addWidget(self._create_btn)
        inner.addWidget(self._unlock_btn)

        inner.addSpacing(8)
        self._state_label = QLabel(
            "Your vault is encrypted locally.\nYour master password is never stored."
        )
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setProperty("muted", True)
        inner.addWidget(self._state_label)

        version = QLabel(f"v{APP_VERSION} · {VAULT_DB_PATH.name}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setProperty("muted", True)
        inner.addWidget(version)

    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh_state()

    def _refresh_state(self) -> None:
        if self._auth is None:
            self._create_btn.setEnabled(False)
            self._unlock_btn.setEnabled(False)
            self._state_label.setText(self._start_error or "Vault unavailable.")
            self._state_label.setProperty("danger", True)
            self._repolish(self._state_label)
            return
        exists = self._auth.vault_exists
        self._unlock_btn.setEnabled(exists)
        primary = self._create_btn if not exists else self._unlock_btn
        secondary = self._unlock_btn if not exists else self._create_btn
        primary.setObjectName("primaryButton")
        secondary.setObjectName("")
        self._repolish(primary, secondary)
        self._state_label.setProperty("muted", True)
        self._state_label.setStyleSheet("")
        self._state_label.setText(
            "A vault already exists on this device.\n"
            "Your vault is encrypted locally. Your master password is never stored."
            if exists
            else "No vault exists yet.\n"
            "Your vault is encrypted locally. Your master password is never stored."
        )
        self._repolish(self._state_label)

    @staticmethod
    def _repolish(*widgets: QWidget) -> None:
        style = QApplication.style()
        for widget in widgets:
            style.unpolish(widget)
            style.polish(widget)
        for widget in widgets:
            widget.update()

    # ------------------------------------------------------------------
    def _create_vault(self) -> None:
        dialog = SetupWindow(self._auth, self)
        if dialog.exec():
            self._unlock_vault(note="Vault created successfully. Unlock it below.")

    def _unlock_vault(self, note: str | None = None) -> None:
        dialog = UnlockWindow(self._auth, self, note=note)
        if dialog.exec() and dialog.session_key:
            self._open_main(dialog.session_key)
        else:
            self._refresh_state()

    def _open_main(self, key: bytes) -> None:
        from .main_window import MainWindow

        try:
            window = MainWindow(
                self._auth,
                self._settings,
                key,
                on_return_to_welcome=self.show,
            )
        except Exception:
            QMessageBox.critical(self, APP_NAME, "Unable to open the vault database.")
            return
        self._main = window
        window.destroyed.connect(self._clear_main_ref)
        window.show()
        self.hide()

    def _clear_main_ref(self) -> None:
        self._main = None
