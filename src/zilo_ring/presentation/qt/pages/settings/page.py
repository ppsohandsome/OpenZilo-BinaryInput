from __future__ import annotations

from PySide6.QtWidgets import QLabel, QFormLayout, QWidget

from zilo_ring.config import Settings
from zilo_ring.state import StoreSnapshot


class SettingsPage(QWidget):
    page_id = "settings"
    title = "Settings"
    subtitle = ""

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(12, 10, 12, 0)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(4)
        layout.addRow("SDK", QLabel("OpenZilo Python SDK"))
        layout.addRow("Scan timeout", QLabel(f"{settings.scan_timeout_s:.1f} s"))
        layout.addRow("Sample timeout", QLabel(f"{settings.sample_timeout_s:.1f} s"))
        layout.addRow("Stale threshold", QLabel(f"{settings.stale_after_ms:.0f} ms"))
        layout.addRow("Orientation alpha", QLabel(f"{settings.orientation_alpha:.2f}"))
        layout.addRow("GUI refresh", QLabel(f"{settings.gui_refresh_hz} Hz"))
        layout.addRow("Capture output", QLabel(str(settings.capture_dir)))
        layout.addRow("Recognition log", QLabel(str(settings.recognition_log_path)))
        layout.addRow("Configuration", QLabel("Environment variables; editable UI comes later"))

    def refresh(self, snapshot: StoreSnapshot) -> None:
        return None
