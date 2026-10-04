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
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from zilo_ring.application import RingController
from zilo_ring.capture import CaptureRecorder
from zilo_ring.config import Settings
from zilo_ring.domain import ConnectionState
from zilo_ring.presentation.qt.pages.capture import CapturePage
from zilo_ring.presentation.qt.pages.morse import MorseInputPage
from zilo_ring.presentation.qt.pages.settings import SettingsPage
from zilo_ring.presentation.qt.pages.visualization import VisualizationPage
from zilo_ring.presentation.qt.theme import MUTED, application_stylesheet, data_font, ui_font
from zilo_ring.state import AppStore

from .page_registry import PageRegistry


class UIContext(Protocol):
    settings: Settings
    store: AppStore
    controller: RingController
    capture_recorder: CaptureRecorder
    demo: bool


class MainWindow(QMainWindow):
    def __init__(self, context: UIContext) -> None:
        super().__init__()
        self.context = context
        self.registry = PageRegistry()
        self._last_badge_state: ConnectionState | None = None
        self._last_metrics_update_ns = 0
        self._close_pending = False
        self.setWindowTitle("Zilo Ring")
        self.resize(1380, 820)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_body(), 1)
        root_layout.addWidget(self._build_status_bar())
        self.setCentralWidget(root)
        self._apply_style()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(max(1, round(1000 / context.settings.gui_refresh_hz)))
        self.navigation.setCurrentRow(0)
        QTimer.singleShot(0, self._set_default_workspace_split)

    def _build_header(self) -> QWidget:
        header = QFrame()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        title = QLabel("ZILO RING")
        title.setObjectName("title")
        title.setFont(ui_font(18, QFont.Weight.Medium))
        layout.addWidget(title)
        layout.addStretch(1)

        self.mac_input = QLineEdit(self.context.settings.ring_mac)
        self.mac_input.setPlaceholderText("Ring MAC (empty = virtual)")
        self.mac_input.setMinimumWidth(190)
        self.connect_button = QPushButton("Connect")
        self.stop_button = QPushButton("Stop")
        self.recenter_button = QPushButton("Recenter")
        for button in (
            self.connect_button,
            self.stop_button,
            self.recenter_button,
        ):
            button.setFixedWidth(88)
        self.connect_button.clicked.connect(self._connect)
        self.stop_button.clicked.connect(self.context.controller.stop)
        self.recenter_button.clicked.connect(self.context.controller.recenter)
        layout.addWidget(self.mac_input)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.recenter_button)
        return header

    def _connect(self) -> None:
        if self.context.controller.start(self.mac_input.text()):
            self.connect_button.setEnabled(False)
            self.mac_input.setEnabled(False)

    def _build_body(self) -> QWidget:
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFixedWidth(176)
        self.pages = QStackedWidget()
        self.capture_page = CapturePage(self.context.capture_recorder)
        self.visualization_panel = VisualizationPage()

        for page in (
            self.capture_page,
            MorseInputPage(),
            SettingsPage(self.context.settings),
        ):
            entry = self.registry.register(page)
            self.navigation.addItem(entry.title)
            self.pages.addWidget(entry.widget)

        self.navigation.currentRowChanged.connect(self._show_page)
        self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        self.workspace_splitter.setObjectName("workspaceSplitter")
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(6)
        self.workspace_splitter.addWidget(self._build_page_workspace())
        self.workspace_splitter.addWidget(self.visualization_panel)
        self.workspace_splitter.setStretchFactor(0, 2)
        self.workspace_splitter.setStretchFactor(1, 3)
        self.workspace_splitter.setSizes([400, 600])
        layout.addWidget(self.navigation)
        layout.addWidget(self.workspace_splitter, 1)
        return body

    def _build_page_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        header_host = QWidget()
        header_layout = QHBoxLayout(header_host)
        header_layout.setContentsMargins(0, 12, 0, 0)
        page_header = QFrame()
        page_header.setObjectName("sectionHeader")
        page_header.setFixedHeight(36)
        page_header_layout = QHBoxLayout(page_header)
        page_header_layout.setContentsMargins(12, 0, 12, 0)
        page_header_layout.setSpacing(12)
        self.page_title = QLabel()
        self.page_title.setFont(ui_font(13, QFont.Weight.Medium))
        self.page_subtitle = QLabel()
        self.page_subtitle.setStyleSheet(f"color: {MUTED};")
        page_header_layout.addWidget(self.page_title)
        page_header_layout.addWidget(self.page_subtitle)
        page_header_layout.addStretch(1)
        header_layout.addWidget(page_header)

        workspace_layout.addWidget(header_host)
        workspace_layout.addWidget(self.pages, 1)
        return workspace

    def _show_page(self, index: int) -> None:
        if not 0 <= index < len(self.registry.entries):
            return
        entry = self.registry.entries[index]
        self.pages.setCurrentIndex(index)
        self.page_title.setText(entry.title)
        self.page_subtitle.setText(entry.subtitle)
        self.page_subtitle.setVisible(bool(entry.subtitle))
        activate = getattr(entry.widget, "activate", None)
        if activate is not None:
            activate(self.context.store.snapshot())

    def _build_status_bar(self) -> QWidget:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.status_badge = QLabel("IDLE")
        self.status_badge.setObjectName("statusBadge")
        self.status_text = QLabel("Not connected")
        self.metrics_text = QLabel(_format_metrics(0.0, None, 0, 0))
        metrics_font = data_font(10)
        self.battery_text = QLabel(_format_battery(None))
        self.battery_text.setObjectName("batteryStatus")
        self.battery_text.setFont(metrics_font)
        self.battery_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.battery_text.setFixedWidth(
            QFontMetrics(metrics_font).horizontalAdvance(_format_battery(100)) + 36
        )
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
        layout.addWidget(self.battery_text)
        layout.addWidget(self.metrics_text)
        return frame

    def _set_default_workspace_split(self) -> None:
        available = sum(self.workspace_splitter.sizes())
        upper = round(available * 0.4)
        self.workspace_splitter.setSizes([upper, available - upper])

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
        running = self.context.controller.running
        self.connect_button.setEnabled(not running and not self._close_pending)
        self.stop_button.setEnabled(
            running and ring.state != ConnectionState.STOPPING and not self._close_pending
        )
        self.mac_input.setEnabled(not running and not self._close_pending)
        now_ns = time.monotonic_ns()
        if state_changed or now_ns - self._last_metrics_update_ns >= 100_000_000:
            self.battery_text.setText(_format_battery(ring.battery_percent))
            self.metrics_text.setText(
                _format_metrics(
                    ring.receive_rate_hz,
                    ring.data_age_ms,
                    ring.dropped_samples,
                    ring.reconnect_count,
                )
            )
            self._last_metrics_update_ns = now_ns
        self.capture_page.refresh(snapshot)
        page = self.pages.currentWidget()
        if page is not self.capture_page:
            refresh = getattr(page, "refresh", None)
            if refresh is not None:
                refresh(snapshot)
        self.visualization_panel.refresh(snapshot)
        if self._close_pending and not running:
            self._close_pending = False
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.context.controller.running:
            self._close_pending = True
            self.context.controller.stop()
            self.setEnabled(False)
            event.ignore()
            return
        if self.context.capture_recorder.status.recording:
            try:
                self.context.capture_recorder.stop()
            except RuntimeError:
                pass
        event.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet(application_stylesheet())


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


def _format_battery(battery_percent: int | None) -> str:
    value = " --" if battery_percent is None else f"{battery_percent:3d}"
    return f"BATTERY {value}%"
