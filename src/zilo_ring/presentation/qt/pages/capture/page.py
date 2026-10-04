from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from zilo_ring.capture import CaptureRecorder
from zilo_ring.capture.recorder import (
    CAPTURE_AMPLITUDE_OPTIONS,
    CAPTURE_AMPLITUDE_DISPLAY,
    CAPTURE_HAND_ANGLES_DEG,
    CAPTURE_LABEL_DISPLAY,
    CAPTURE_LABEL_OPTIONS,
    CAPTURE_NEGATIVE_LABELS,
    CAPTURE_NEGATIVE_TYPE_OPTIONS,
    CAPTURE_NEGATIVE_TYPE_DISPLAY,
    CAPTURE_SPEED_DISPLAY,
    CAPTURE_SPEED_OPTIONS,
    NOT_APPLICABLE_NEGATIVE_TYPE,
)
from zilo_ring.domain import ConnectionState
from zilo_ring.presentation.qt.theme import (
    ACCENT,
    ACCENT_DARK,
    BORDER,
    MUTED,
    SURFACE_RAISED,
    TEXT,
    data_font,
)
from zilo_ring.state import StoreSnapshot


class CapturePage(QWidget):
    page_id = "capture"
    title = "Capture"
    subtitle = "Still 1 s → move once → hold 1 s → Stop; reset only after saving."

    def __init__(self, recorder: CaptureRecorder, parent=None) -> None:
        super().__init__(parent)
        self._recorder = recorder
        self._has_imu = False
        self._latest_received_ns: int | None = None
        self._last_ui_update_ns = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.label_combo = QComboBox()
        for value, display in CAPTURE_LABEL_OPTIONS:
            self.label_combo.addItem(display, value)
        self.label_combo.currentIndexChanged.connect(
            self._update_negative_type_visibility
        )

        self.angle_combo = QComboBox()
        for angle in CAPTURE_HAND_ANGLES_DEG:
            self.angle_combo.addItem(f"{angle:+d}°" if angle else "0°", angle)

        self.speed_combo = QComboBox()
        for value, display in CAPTURE_SPEED_OPTIONS:
            self.speed_combo.addItem(display, value)

        self.amplitude_combo = QComboBox()
        for value, display in CAPTURE_AMPLITUDE_OPTIONS:
            self.amplitude_combo.addItem(display, value)

        self.negative_type_label = QLabel("负样本类型")
        self.negative_type_combo = QComboBox()
        for value, display in CAPTURE_NEGATIVE_TYPE_OPTIONS:
            self.negative_type_combo.addItem(display, value)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("可选备注")

        metadata = QHBoxLayout()
        metadata.setSpacing(8)
        metadata.addWidget(QLabel("动作标签"))
        metadata.addWidget(self.label_combo)
        metadata.addWidget(QLabel("手部角度"))
        metadata.addWidget(self.angle_combo)
        metadata.addWidget(QLabel("速度"))
        metadata.addWidget(self.speed_combo)
        metadata.addWidget(QLabel("幅度"))
        metadata.addWidget(self.amplitude_combo)
        metadata.addStretch(1)

        detail_metadata = QHBoxLayout()
        detail_metadata.setSpacing(8)
        detail_metadata.addWidget(self.negative_type_label)
        detail_metadata.addWidget(self.negative_type_combo)
        detail_metadata.addWidget(QLabel("备注"))
        detail_metadata.addWidget(self.notes_input, 1)
        self._update_negative_type_visibility()

        self.start_button = QPushButton("Start recording")
        self.retake_button = QPushButton("Retake current")
        self.stop_button = QPushButton("Stop and save")
        for button in (
            self.start_button,
            self.retake_button,
            self.stop_button,
        ):
            button.setFixedWidth(122)
        self.retake_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self._start)
        self.retake_button.clicked.connect(self._retake)
        self.stop_button.clicked.connect(self._stop)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.start_button)
        controls.addWidget(self.retake_button)
        controls.addWidget(self.stop_button)

        self.recording_badge = QLabel("READY")
        self.recording_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recording_badge.setFixedWidth(110)
        self.recording_badge.setFixedHeight(34)
        self.recording_badge.setStyleSheet(
            f"background: {SURFACE_RAISED}; color: {MUTED}; "
            f"border: 1px solid {BORDER}; border-radius: 1px; "
            "padding: 0 12px; font-weight: 500;"
        )
        self.status_text = QLabel("Connect the ring, then start a trial.")
        self.metrics = QLabel("samples: 0    duration: 0.00 s")
        self.metrics.setFont(data_font(12))
        controls.addWidget(self.recording_badge)
        controls.addWidget(self.status_text, 1)
        controls.addWidget(self.metrics)

        self.saved_path = QLabel(f"output: {self._recorder.output_dir}")
        self.saved_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.saved_path.setStyleSheet(f"color: {MUTED};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addLayout(metadata)
        layout.addLayout(detail_metadata)
        layout.addLayout(controls)
        layout.addWidget(self.saved_path)

    def refresh(self, snapshot: StoreSnapshot) -> None:
        self._has_imu = (
            snapshot.ring.latest_sample is not None
            and snapshot.ring.state == ConnectionState.STREAMING
        )
        self._latest_received_ns = (
            None
            if snapshot.ring.latest_sample is None
            else snapshot.ring.latest_sample.received_timestamp_ns
        )
        self._recorder.ingest(
            snapshot.history,
            snapshot.bias_corrected_history,
        )
        now_ns = time.monotonic_ns()
        if now_ns - self._last_ui_update_ns < 100_000_000:
            return
        self._last_ui_update_ns = now_ns
        self._refresh_status()

    def _start(self) -> None:
        if not self._has_imu:
            self.status_text.setText("No IMU samples. Connect the ring first.")
            return
        try:
            self._recorder.start(
                label=str(self.label_combo.currentData()),
                speed=str(self.speed_combo.currentData()),
                amplitude=str(self.amplitude_combo.currentData()),
                hand_angle_deg=int(self.angle_combo.currentData()),
                negative_type=(
                    str(self.negative_type_combo.currentData())
                    if self.label_combo.currentData() in CAPTURE_NEGATIVE_LABELS
                    else NOT_APPLICABLE_NEGATIVE_TYPE
                ),
                notes=self.notes_input.text(),
                exclude_through_received_ns=self._latest_received_ns,
            )
        except (RuntimeError, ValueError) as exc:
            self.status_text.setText(str(exc))
            return
        self.label_combo.setEnabled(False)
        self.angle_combo.setEnabled(False)
        self.speed_combo.setEnabled(False)
        self.amplitude_combo.setEnabled(False)
        self.negative_type_combo.setEnabled(False)
        self.notes_input.setEnabled(False)
        self.start_button.setEnabled(False)
        self.retake_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self._refresh_status()

    def _retake(self) -> None:
        try:
            self._recorder.restart(
                exclude_through_received_ns=self._latest_received_ns,
            )
        except RuntimeError as exc:
            self.status_text.setText(str(exc))
            return
        self._refresh_status()

    def _stop(self) -> None:
        try:
            path = self._recorder.stop()
        except RuntimeError as exc:
            self.status_text.setText(str(exc))
        else:
            self.status_text.setText("Saved successfully")
            self.saved_path.setText(f"saved: {path}")
        self.label_combo.setEnabled(True)
        self.angle_combo.setEnabled(True)
        self.speed_combo.setEnabled(True)
        self.amplitude_combo.setEnabled(True)
        self.negative_type_combo.setEnabled(True)
        self.notes_input.setEnabled(True)
        self.start_button.setEnabled(True)
        self.retake_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self._recorder.status
        self.metrics.setText(
            f"samples: {status.sample_count}    duration: {status.duration_s:.2f} s"
        )
        if status.recording:
            angle_text = (
                f"{status.hand_angle_deg:+d}°" if status.hand_angle_deg else "0°"
            )
            negative_text = (
                " / "
                + CAPTURE_NEGATIVE_TYPE_DISPLAY.get(
                    status.negative_type, status.negative_type
                )
                if status.label in CAPTURE_NEGATIVE_LABELS
                else ""
            )
            self.recording_badge.setText("RECORDING")
            self.recording_badge.setStyleSheet(
                f"background: {ACCENT}; color: white; border-radius: 1px; "
                "padding: 0 12px; font-weight: 500;"
            )
            self.status_text.setText(
                f"{status.message}: "
                f"{CAPTURE_LABEL_DISPLAY.get(status.label, status.label)} / "
                f"{angle_text} / "
                f"{CAPTURE_SPEED_DISPLAY.get(status.speed, status.speed)} / "
                f"{CAPTURE_AMPLITUDE_DISPLAY.get(status.amplitude, status.amplitude)}"
                f"{negative_text}"
            )
        else:
            self.recording_badge.setText("READY")
            self.recording_badge.setStyleSheet(
                f"background: {ACCENT_DARK}; color: {TEXT}; "
                f"border: 1px solid {ACCENT}; border-radius: 1px; "
                "padding: 0 12px; font-weight: 500;"
            )

    def _update_negative_type_visibility(self) -> None:
        visible = self.label_combo.currentData() in CAPTURE_NEGATIVE_LABELS
        self.negative_type_label.setVisible(visible)
        self.negative_type_combo.setVisible(visible)
