"""Application entry point: launch the welcome window."""

from __future__ import annotations

import sys


def main() -> int:
    from app.config import APP_NAME
    from app.utils import configure_logging
    from app.config import load_settings

    configure_logging()

    try:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "PySide6 is not installed. Run: pip install -r requirements.txt\n"
        )
        return 1

    from ui.styles import create_app_icon
    from ui.theme import set_app_theme
    from ui.welcome_window import WelcomeWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    settings = load_settings()
    set_app_theme(app, settings.theme)
    app.setWindowIcon(create_app_icon())

    window = WelcomeWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
