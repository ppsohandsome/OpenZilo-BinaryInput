from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from zilo_ring.domain import DetectedAction, IMUSample, Vector3
from zilo_ring.presentation.qt.theme import (
    ACCENT,
    AXIS_BLUE,
    AXIS_GREEN,
    AXIS_RED,
    BACKGROUND,
    BORDER,
    GRID,
    GRID_STRONG,
    MUTED,
    TEXT,
    data_font,
)


PLOT_WINDOW_MS = 5_000
ACCEL_RANGE_G = 2.0
GYRO_RANGE_DPS = 500.0
AXIS_COLORS = (QColor(AXIS_RED), QColor(AXIS_GREEN), QColor(AXIS_BLUE))
AXIS_NAMES = ("X", "Y", "Z")
class SensorCharts(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(460, 260)
        self._canvas = _SensorChartCanvas()
        self.accel_raw_button = QPushButton("raw")
        self.accel_bias_button = QPushButton("bias")
        self.gyro_raw_button = QPushButton("raw")
        self.gyro_bias_button = QPushButton("bias")
        for button in (
            self.accel_raw_button,
            self.accel_bias_button,
            self.gyro_raw_button,
            self.gyro_bias_button,
        ):
            button.setObjectName("seriesToggle")
            button.setCheckable(True)
            button.setChecked(True)
            button.setFixedSize(58, 32)
        self.accel_raw_button.toggled.connect(self._set_accel_raw_visible)
        self.accel_bias_button.toggled.connect(self._set_accel_bias_visible)
        self.gyro_raw_button.toggled.connect(self._set_gyro_raw_visible)
        self.gyro_bias_button.toggled.connect(self._set_gyro_bias_visible)

        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(6)
        controls.setVerticalSpacing(3)
        controls.setColumnStretch(3, 1)
        controls.addWidget(QLabel("ACCELERATION"), 0, 0)
        controls.addWidget(self.accel_raw_button, 0, 1)
        controls.addWidget(self.accel_bias_button, 0, 2)
        controls.addWidget(QLabel("GYROSCOPE"), 1, 0)
        controls.addWidget(self.gyro_raw_button, 1, 1)
        controls.addWidget(self.gyro_bias_button, 1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        layout.addLayout(controls)
        layout.addWidget(self._canvas, 1)

    def set_history(
        self,
        raw_history: tuple[IMUSample, ...],
        bias_corrected_history: tuple[IMUSample, ...],
        detected_actions: tuple[DetectedAction, ...] = (),
    ) -> None:
        self._canvas.set_history(raw_history, bias_corrected_history, detected_actions)

    def _set_accel_raw_visible(self, visible: bool) -> None:
        self._canvas.set_accel_raw_visible(visible)

    def _set_accel_bias_visible(self, visible: bool) -> None:
        self._canvas.set_accel_bias_visible(visible)

    def _set_gyro_raw_visible(self, visible: bool) -> None:
        self._canvas.set_gyro_raw_visible(visible)

    def _set_gyro_bias_visible(self, visible: bool) -> None:
        self._canvas.set_gyro_bias_visible(visible)


class _SensorChartCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._raw_history: tuple[IMUSample, ...] = ()
        self._bias_corrected_history: tuple[IMUSample, ...] = ()
        self._detected_actions: tuple[DetectedAction, ...] = ()
        self._show_accel_raw = True
        self._show_accel_bias = True
        self._show_gyro_raw = True
        self._show_gyro_bias = True

    def set_history(
        self,
        raw_history: tuple[IMUSample, ...],
        bias_corrected_history: tuple[IMUSample, ...],
        detected_actions: tuple[DetectedAction, ...],
    ) -> None:
        self._raw_history = _windowed_history(raw_history, PLOT_WINDOW_MS)
        self._bias_corrected_history = _windowed_history(
            bias_corrected_history,
            PLOT_WINDOW_MS,
        )
        self._detected_actions = detected_actions
        self.update()

    def set_accel_raw_visible(self, visible: bool) -> None:
        self._show_accel_raw = visible
        self.update()

    def set_accel_bias_visible(self, visible: bool) -> None:
        self._show_accel_bias = visible
        self.update()

    def set_gyro_raw_visible(self, visible: bool) -> None:
        self._show_gyro_raw = visible
        self.update()

    def set_gyro_bias_visible(self, visible: bool) -> None:
        self._show_gyro_bias = visible
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BACKGROUND))
        left = 54.0
        right = 18.0
        top = 48.0
        bottom = 30.0
        gap = 66.0
        chart_height = (self.height() - top - bottom - gap) / 2
        accel_rect = QRectF(left, top, self.width() - left - right, chart_height)
        gyro_rect = QRectF(left, top + chart_height + gap, self.width() - left - right, chart_height)
        self._draw_chart(
            painter,
            accel_rect,
            "ACCELERATION",
            "g",
            ACCEL_RANGE_G,
            lambda sample: sample.accel_g,
            show_raw=self._show_accel_raw,
            show_bias=self._show_accel_bias,
            show_action_labels=True,
        )
        self._draw_chart(
            painter,
            gyro_rect,
            "GYROSCOPE",
            "°/s",
            GYRO_RANGE_DPS,
            lambda sample: sample.gyro_dps,
            show_raw=self._show_gyro_raw,
            show_bias=self._show_gyro_bias,
            show_action_labels=False,
        )
        painter.end()

    def _draw_chart(
        self,
        painter: QPainter,
        rect: QRectF,
        title: str,
        unit: str,
        value_range: float,
        getter: Callable[[IMUSample], Vector3],
        *,
        show_raw: bool,
        show_bias: bool,
        show_action_labels: bool,
    ) -> None:
        painter.setFont(data_font(9))
        painter.setPen(QPen(QColor(BORDER), 1.0))
        painter.drawRect(rect)

        for step in range(5):
            fraction = step / 4.0
            y = rect.top() + fraction * rect.height()
            grid_color = QColor(GRID_STRONG) if step == 2 else QColor(GRID)
            painter.setPen(QPen(grid_color, 1.2 if step == 2 else 1.0))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
            value = value_range * (1.0 - fraction * 2.0)
            painter.setPen(QColor(MUTED))
            painter.drawText(
                QRectF(2, y - 8, rect.left() - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:g}",
            )

        for step in range(6):
            fraction = step / 5.0
            x = rect.left() + fraction * rect.width()
            painter.setPen(QPen(QColor(GRID), 1.0))
            painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            seconds = -5.0 + fraction * 5.0
            label = "now" if step == 5 else f"{seconds:.0f}s"
            painter.setPen(QColor(MUTED))
            painter.drawText(
                QRectF(x - 18, rect.bottom() + 3, 36, 15),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        painter.setPen(QColor(TEXT))
        painter.drawText(
            QRectF(rect.left(), rect.top() - 43, rect.width(), 17),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{title}  ±{value_range:g} {unit}",
        )
        self._draw_values(painter, rect, getter)
        if not show_raw and not show_bias:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "both series hidden")
            return
        if max(len(self._raw_history), len(self._bias_corrected_history)) < 2:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for IMU")
            return

        active_history = self._raw_history or self._bias_corrected_history
        latest_timestamp_ms = active_history[-1].device_timestamp_ms
        oldest_timestamp_ms = latest_timestamp_ms - PLOT_WINDOW_MS
        painter.save()
        painter.setClipRect(rect)
        self._draw_actions(
            painter,
            rect,
            oldest_timestamp_ms,
            latest_timestamp_ms,
            show_labels=show_action_labels,
        )
        for axis, color in enumerate(AXIS_COLORS):
            if show_raw:
                raw_color = QColor(color)
                raw_color.setAlpha(150)
                raw_pen = QPen(raw_color, 1.15, Qt.PenStyle.DashLine)
                self._draw_series(
                    painter,
                    rect,
                    self._raw_history,
                    getter,
                    axis,
                    value_range,
                    oldest_timestamp_ms,
                    raw_pen,
                )
            if show_bias:
                self._draw_series(
                    painter,
                    rect,
                    self._bias_corrected_history,
                    getter,
                    axis,
                    value_range,
                    oldest_timestamp_ms,
                    QPen(color, 1.7, Qt.PenStyle.SolidLine),
                )
        painter.restore()

    def _draw_actions(
        self,
        painter: QPainter,
        rect: QRectF,
        oldest_timestamp_ms: int,
        latest_timestamp_ms: int,
        *,
        show_labels: bool,
    ) -> None:
        colors = {
            "up": QColor("#d97a91"),
            "down": QColor("#b95a74"),
            "single_press_rebound": QColor(ACCENT),
            "up_flick_rebound": QColor("#e4879d"),
            "double_press_rebound": QColor("#b9789b"),
            "rejected": QColor("#776c72"),
        }
        display_labels = {
            "up": "向上",
            "down": "向下",
            "single_press_rebound": "单次按压回弹",
            "up_flick_rebound": "向上弹指回弹",
            "double_press_rebound": "快速双次按压回弹",
            "gesture_negative_v2": "负样本",
            "rejected": "拒绝",
        }
        for action in self._detected_actions:
            if (
                action.end_device_timestamp_ms < oldest_timestamp_ms
                or action.start_device_timestamp_ms > latest_timestamp_ms
            ):
                continue
            start_fraction = (
                action.start_device_timestamp_ms - oldest_timestamp_ms
            ) / PLOT_WINDOW_MS
            end_fraction = (
                action.end_device_timestamp_ms - oldest_timestamp_ms
            ) / PLOT_WINDOW_MS
            left = rect.left() + min(1.0, max(0.0, start_fraction)) * rect.width()
            right = rect.left() + min(1.0, max(0.0, end_fraction)) * rect.width()
            action_rect = QRectF(left, rect.top(), max(3.0, right - left), rect.height())
            color = colors.get(action.label, QColor(ACCENT))
            fill = QColor(color)
            fill.setAlpha(34)
            outline = QColor(color)
            outline.setAlpha(220)
            painter.fillRect(action_rect, fill)
            painter.setPen(QPen(outline, 1.6))
            painter.drawRect(action_rect)
            if show_labels:
                display_label = display_labels.get(action.label, action.label)
                if action.label == "rejected":
                    candidate = display_labels.get(
                        action.candidate_label, action.candidate_label
                    )
                    display_label = f"拒绝({candidate})"
                painter.setPen(color)
                painter.setFont(data_font(8, QFont.Weight.Medium))
                painter.drawText(
                    QRectF(action_rect.left() + 4, action_rect.top() + 3, 340, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    (
                        f"{display_label} (conf {action.similarity:.2f}) · "
                        f"{action.duration_s:.2f}s · "
                        f"margin {action.direction_coherence:.2f}"
                    ),
                )

    def _draw_values(
        self,
        painter: QPainter,
        rect: QRectF,
        getter: Callable[[IMUSample], Vector3],
    ) -> None:
        raw_values = (0.0, 0.0, 0.0)
        bias_values = (0.0, 0.0, 0.0)
        if self._raw_history:
            raw_values = getter(self._raw_history[-1]).as_tuple()
        if self._bias_corrected_history:
            bias_values = getter(self._bias_corrected_history[-1]).as_tuple()

        cell_width = rect.width() / 3.0
        painter.setFont(data_font(8))
        for index, (name, color, raw, bias) in enumerate(
            zip(
                AXIS_NAMES,
                AXIS_COLORS,
                raw_values,
                bias_values,
                strict=True,
            )
        ):
            painter.setPen(color)
            painter.drawText(
                QRectF(
                    rect.left() + index * cell_width,
                    rect.top() - 24,
                    cell_width,
                    18,
                ),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                f"{name} {raw:+.2f}/{bias:+.2f}",
            )

    @staticmethod
    def _draw_series(
        painter: QPainter,
        rect: QRectF,
        history: tuple[IMUSample, ...],
        getter: Callable[[IMUSample], Vector3],
        axis: int,
        value_range: float,
        oldest_timestamp_ms: int,
        pen: QPen,
    ) -> None:
        painter.setPen(pen)
        path = QPainterPath()
        has_point = False
        for sample in history:
            value = getter(sample).as_tuple()[axis]
            fraction = (sample.device_timestamp_ms - oldest_timestamp_ms) / PLOT_WINDOW_MS
            x = rect.left() + min(1.0, max(0.0, fraction)) * rect.width()
            bounded_value = min(value_range, max(-value_range, value))
            y = rect.center().y() - bounded_value / value_range * rect.height() * 0.5
            current = QPointF(x, y)
            if has_point:
                path.lineTo(current)
            else:
                path.moveTo(current)
                has_point = True
        if has_point:
            painter.drawPath(path)

def _windowed_history(
    history: tuple[IMUSample, ...],
    window_ms: int,
) -> tuple[IMUSample, ...]:
    if not history:
        return ()
    cutoff = history[-1].device_timestamp_ms - window_ms
    start = 0
    for index, sample in enumerate(history):
        if sample.device_timestamp_ms >= cutoff:
            start = index
            break
    return history[start:]
