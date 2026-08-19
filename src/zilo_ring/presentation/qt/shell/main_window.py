from __future__ import annotations

import time
from typing import Protocol

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from zilo_ring.application import RingController
from zilo_ring.config import Settings
from zilo_ring.domain import ConnectionState
from zilo_ring.presentation.qt.pages.diagnostics import DiagnosticsPage
from zilo_ring.presentation.qt.pages.settings import SettingsPage
from zilo_ring.presentation.qt.pages.visualization import VisualizationPage
from zilo_ring.state import AppStore

from .page_registry import PageRegistry


class UIContext(Protocol):
    settings: Settings
    store: AppStore
    controller: RingController
    demo: bool


class MainWindow(QMainWindow):
    def __init__(self, context: UIContext) -> None:
        super().__init__()
        self.context = context
        self.registry = PageRegistry()
        self._last_badge_state: ConnectionState | None = None
        self._last_metrics_update_ns = 0
        self.setWindowTitle("Zilo Ring")
        self.resize(1380, 820)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 12)
        root_layout.setSpacing(12)
        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_body(), 1)
        root_layout.addWidget(self._build_status_bar())
        self.setCentralWidget(root)
        self._apply_style()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(max(1, round(1000 / context.settings.gui_refresh_hz)))
        self.navigation.setCurrentRow(0)

    def _build_header(self) -> QWidget:
        header = QFrame()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)
        title = QLabel("ZILO RING")
        title.setObjectName("title")
        title.setFont(QFont("sans-serif", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch(1)

        self.mac_input = QLineEdit(
            self.context.settings.ring_mac or ("DE:MO:00:00:00:01" if self.context.demo else "")
        )
        self.mac_input.setPlaceholderText("Ring MAC address")
        self.mac_input.setMinimumWidth(190)
        self.connect_button = QPushButton("Connect")
        self.stop_button = QPushButton("Stop")
        self.recenter_button = QPushButton("Recenter")
        self.connect_button.clicked.connect(
            lambda: self.context.controller.start(self.mac_input.text())
        )
        self.stop_button.clicked.connect(self.context.controller.stop)
        self.recenter_button.clicked.connect(self.context.controller.recenter)
        layout.addWidget(self.mac_input)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.recenter_button)
        return header

    def _build_body(self) -> QWidget:
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFixedWidth(180)
        self.pages = QStackedWidget()

        for page in (
            VisualizationPage(),
            DiagnosticsPage(),
            SettingsPage(self.context.settings),
        ):
            entry = self.registry.register(page)
            self.navigation.addItem(entry.title)
            self.pages.addWidget(entry.widget)

        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        return body

    def _build_status_bar(self) -> QWidget:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 6, 12, 6)
        self.status_badge = QLabel("IDLE")
        self.status_badge.setObjectName("statusBadge")
        self.status_text = QLabel("Not connected")
        self.metrics_text = QLabel(_format_metrics(0.0, None, 0, 0))
        metrics_font = QFont("monospace", 10)
        self.metrics_text.setFont(metrics_font)
        self.metrics_text.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        reserved_text = _format_metrics(999.9, 99_999.9, 999_999, 9_999)
        self.metrics_text.setFixedWidth(
            QFontMetrics(metrics_font).horizontalAdvance(reserved_text) + 12
        )
        layout.addWidget(self.status_badge)
        layout.addWidget(self.status_text)
        layout.addStretch(1)
        layout.addWidget(self.metrics_text)
        return frame

    def _refresh(self) -> None:
        snapshot = self.context.store.snapshot()
        ring = snapshot.ring
        state_changed = ring.state != self._last_badge_state
        if state_changed:
            self.status_badge.setText(ring.state.upper())
            self.status_badge.setProperty("streaming", ring.state == ConnectionState.STREAMING)
            self.status_badge.style().unpolish(self.status_badge)
            self.status_badge.style().polish(self.status_badge)
            self._last_badge_state = ring.state
        self.status_text.setText(ring.message)
        now_ns = time.monotonic_ns()
        if state_changed or now_ns - self._last_metrics_update_ns >= 100_000_000:
            self.metrics_text.setText(
                _format_metrics(
                    ring.receive_rate_hz,
                    ring.data_age_ms,
                    ring.dropped_samples,
                    ring.reconnect_count,
                )
            )
            self._last_metrics_update_ns = now_ns
        page = self.pages.currentWidget()
        refresh = getattr(page, "refresh", None)
        if refresh is not None:
            refresh(snapshot)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.context.controller.stop()
        event.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0d141b; color: #d7e1ea; }
            QFrame { background: #151f29; border: 1px solid #243444; border-radius: 8px; }
            #title { color: #f4f7fa; border: none; }
            #navigation { background: #151f29; border: 1px solid #243444; border-radius: 8px; padding: 8px; }
            #navigation::item { padding: 12px; margin: 2px; border-radius: 5px; }
            #navigation::item:selected { background: #245b78; color: white; }
            QPushButton { background: #22394a; border: 1px solid #36556b; border-radius: 5px; padding: 7px 14px; }
            QPushButton:hover { background: #2c4b61; }
            QLineEdit { background: #0f1820; border: 1px solid #36556b; border-radius: 5px; padding: 7px; }
            #statusBadge { background: #384857; border-radius: 9px; padding: 3px 9px; font-weight: bold; }
            #statusBadge[streaming="true"] { background: #176b4d; color: #eafff6; }
            """
        )


def _format_metrics(
    receive_rate_hz: float,
    data_age_ms: float | None,
    dropped_samples: int,
    reconnect_count: int,
) -> str:
    age = "    -.-" if data_age_ms is None else f"{data_age_ms:7.1f}"
    return (
        f"{receive_rate_hz:6.1f} Hz · age {age} ms · "
        f"lost {dropped_samples:6d} · reconnect {reconnect_count:4d}"
    )
