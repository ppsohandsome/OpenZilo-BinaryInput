from __future__ import annotations

import time

from PySide6.QtWidgets import QHBoxLayout, QWidget

from zilo_ring.state import StoreSnapshot

from .ring_view import RingView
from .sensor_charts import SensorCharts


class VisualizationPage(QWidget):
    page_id = "visualization"
    title = "Visualizer"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_chart_update_ns = 0
        self.ring_view = RingView()
        self.sensor_charts = SensorCharts()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.ring_view, 3)
        layout.addWidget(self.sensor_charts, 2)

    def refresh(self, snapshot: StoreSnapshot) -> None:
        self.ring_view.set_orientation(snapshot.ring.orientation)
        self.ring_view.set_motion(snapshot.ring.motion)
        now_ns = time.monotonic_ns()
        if now_ns - self._last_chart_update_ns >= 33_000_000:
            self.sensor_charts.set_history(snapshot.history)
            self._last_chart_update_ns = now_ns
