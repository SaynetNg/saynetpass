"""Password strength meter and revealed password field widgets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from app.utils import evaluate_password_strength

LEVEL_COLORS = ("#E74C3C", "#E67E22", "#F1C40F", "#2ECC71", "#27AE60")


class PasswordStrengthWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._bar = QProgressBar()
        self._bar.setRange(0, 4)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedWidth(180)
        self._bar.setFixedHeight(10)
        self._bar.setAccessibleName("Password strength meter")

        self._label = QLabel("No password")
        self._label.setProperty("muted", True)

        layout.addWidget(self._bar)
        layout.addWidget(self._label)
        layout.addStretch(1)
        self._set_color(0)

    def _set_color(self, level: int) -> None:
        color = LEVEL_COLORS[min(max(level, 0), len(LEVEL_COLORS) - 1)]
        self._bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")

    def set_password(self, password: str) -> None:
        if not password:
            self._bar.setValue(0)
            self._label.setText("No password")
            self._label.setStyleSheet("")
            return
        result = evaluate_password_strength(password)
        self._bar.setValue(result.level)
        self._label.setText(result.label)
        self._label.setStyleSheet(f"color: {LEVEL_COLORS[result.level]};")
        self._set_color(result.level)


class PasswordField(QWidget):
    """Line edit masked by default with an explicit show/hide toggle."""

    def __init__(self, placeholder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._visible = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.setPlaceholderText(placeholder)
        self._edit.setAccessibleName("Password")

        self._toggle = QPushButton("👁")
        self._toggle.setCheckable(True)
        self._toggle.setFixedWidth(42)
        self._toggle.setProperty("flat", True)
        self._toggle.setToolTip("Show password")
        self._toggle.setAccessibleName("Show password")
        self._toggle.clicked.connect(self._on_toggle)

        layout.addWidget(self._edit, 1)
        layout.addWidget(self._toggle)
        self.setFocusProxy(self._edit)

    def _on_toggle(self) -> None:
        self._visible = self._toggle.isChecked()
        self._edit.setEchoMode(
            QLineEdit.EchoMode.Normal if self._visible else QLineEdit.EchoMode.Password
        )
        self._toggle.setText("🙈" if self._visible else "👁")
        self._toggle.setToolTip("Hide password" if self._visible else "Show password")

    def text(self) -> str:
        return self._edit.text()

    def clear(self) -> None:
        self._edit.clear()

    def line_edit(self) -> QLineEdit:
        return self._edit

    def set_text(self, value: str) -> None:
        self._edit.setText(value)
