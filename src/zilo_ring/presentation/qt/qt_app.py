from __future__ import annotations

import sys
from typing import Any


def run_qt(context: Any) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise SystemExit(
            "PySide6 is not installed. Create a virtual environment and run: "
            "pip install -e '.[dev]'"
        ) from exc

    from zilo_ring.presentation.qt.shell.main_window import MainWindow
    from zilo_ring.presentation.qt.theme import ui_font

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Zilo Ring")
    app.setFont(ui_font(10))
    window = MainWindow(context)
    window.show()
    return app.exec()
