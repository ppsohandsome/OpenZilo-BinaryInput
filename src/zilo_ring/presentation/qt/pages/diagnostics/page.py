from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from zilo_ring.state import StoreSnapshot


class DiagnosticsPage(QWidget):
    page_id = "diagnostics"
    title = "Diagnostics"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._last_update_ns = 0
        self.readout = QLabel("No data")
        self.readout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.readout.setFont(QFont("monospace", 12))
        layout = QVBoxLayout(self)
        layout.addWidget(self.readout)

    def refresh(self, snapshot: StoreSnapshot) -> None:
        now_ns = time.monotonic_ns()
        if now_ns - self._last_update_ns < 100_000_000:
            return
        self._last_update_ns = now_ns
        ring = snapshot.ring
        sample = ring.latest_sample
        raw = "-" if sample is None else (
            f"accel raw: {sample.accel_raw.as_tuple()}\n"
            f"gyro raw:  {sample.gyro_raw.as_tuple()}\n"
            f"sequence:  {sample.sequence}\n"
            f"device ts: {sample.device_timestamp_ms} ms"
        )
        self.readout.setText(
            f"state:          {ring.state}\n"
            f"message:        {ring.message}\n"
            f"address:        {ring.address or '-'}\n"
            f"nominal rate:   {ring.nominal_sample_rate_hz or 0:.1f} Hz\n"
            f"measured rate:  {ring.receive_rate_hz:.1f} Hz\n"
            f"data age:       {ring.data_age_ms if ring.data_age_ms is not None else 0:.1f} ms\n"
            f"dropped:        {ring.dropped_samples}\n"
            f"reconnects:     {ring.reconnect_count}\n"
            f"battery:        {ring.battery_percent if ring.battery_percent is not None else '-'}\n\n"
            f"{raw}"
        )
