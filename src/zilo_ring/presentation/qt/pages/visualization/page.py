from __future__ import annotations

import time

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from zilo_ring.presentation.qt.theme import (
    ACCENT,
    ACCENT_DARK,
    BORDER,
    MUTED,
    TEXT,
)
from zilo_ring.state import StoreSnapshot

from .sensor_charts import SensorCharts


class VisualizationPage(QWidget):
    """Persistent live recognition panel below the replaceable workspace."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_chart_update_ns = 0
        self._last_chart_sequence: int | None = None
        self.recognition_status = QLabel("LIVE RECOGNITION · IDLE")
        self.recognition_status.setObjectName("sectionHeader")
        self.recognition_status.setFixedHeight(36)
        self.recognition_status.setStyleSheet(
            _recognition_header_style(ACCENT_DARK, MUTED, ACCENT)
        )
        self.sensor_charts = SensorCharts()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.recognition_status)
        layout.addWidget(self.sensor_charts, 1)

    def refresh(self, snapshot: StoreSnapshot) -> None:
        self._refresh_recognition_status(snapshot)
        if not snapshot.history:
            return
        latest_sequence = snapshot.history[-1].sequence
        if latest_sequence == self._last_chart_sequence:
            return
        now_ns = time.monotonic_ns()
        if now_ns - self._last_chart_update_ns >= 33_000_000:
            self.sensor_charts.set_history(
                snapshot.history,
                snapshot.bias_corrected_history,
                snapshot.detected_actions,
            )
            self._last_chart_update_ns = now_ns
            self._last_chart_sequence = latest_sequence

    def _refresh_recognition_status(self, snapshot: StoreSnapshot) -> None:
        if snapshot.recognition_active:
            self.recognition_status.setText("LIVE RECOGNITION · MOVING")
            self.recognition_status.setStyleSheet(
                _recognition_header_style(ACCENT_DARK, TEXT, ACCENT)
            )
            return
        latest_device_timestamp_ms = (
            snapshot.history[-1].device_timestamp_ms if snapshot.history else None
        )
        if (
            snapshot.detected_actions
            and latest_device_timestamp_ms is not None
            and latest_device_timestamp_ms
            - snapshot.detected_actions[-1].end_device_timestamp_ms
            <= 1200
        ):
            action = snapshot.detected_actions[-1]
            if action.accepted:
                message = (
                    f"LIVE RECOGNITION · {action.label.upper()} · "
                    f"{action.duration_s:.2f} s · similarity {action.similarity:.3f}"
                )
                color = ACCENT_DARK
            else:
                message = (
                    f"LIVE RECOGNITION · REJECTED ({action.candidate_label.upper()}) · "
                    f"similarity {action.similarity:.3f} · "
                    f"coherence {action.direction_coherence:.3f}"
                )
                color = "#3a3438"
            self.recognition_status.setText(message)
            self.recognition_status.setStyleSheet(
                _recognition_header_style(color, "white", ACCENT)
            )
            return
        self.recognition_status.setText("LIVE RECOGNITION · IDLE")
        self.recognition_status.setStyleSheet(
            _recognition_header_style(ACCENT_DARK, MUTED, ACCENT)
        )


def _recognition_header_style(background: str, color: str, accent: str) -> str:
    return (
        f"background: {background}; color: {color}; "
        f"border: 1px solid {BORDER}; border-left: 2px solid {accent}; "
        "border-radius: 1px; padding: 0 12px; font-weight: 500;"
    )
