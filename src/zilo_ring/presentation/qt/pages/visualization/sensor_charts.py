from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from zilo_ring.domain import IMUSample, Vector3


PLOT_WINDOW_MS = 5_000
ACCEL_RANGE_G = 2.0
GYRO_RANGE_DPS = 500.0
AXIS_COLORS = (QColor("#ff5c5c"), QColor("#58d68d"), QColor("#5dade2"))
AXIS_NAMES = ("X", "Y", "Z")


class SensorCharts(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._history: tuple[IMUSample, ...] = ()
        self.setMinimumSize(460, 420)

    def set_history(self, history: tuple[IMUSample, ...]) -> None:
        self._history = _windowed_history(history, PLOT_WINDOW_MS)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#17212b"))
        left = 54.0
        right = 18.0
        top = 38.0
        bottom = 30.0
        gap = 44.0
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
        )
        self._draw_chart(
            painter,
            gyro_rect,
            "GYROSCOPE",
            "°/s",
            GYRO_RANGE_DPS,
            lambda sample: sample.gyro_dps,
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
    ) -> None:
        painter.setFont(QFont("monospace", 9))
        painter.setPen(QPen(QColor("#2b3d4d"), 1.0))
        painter.drawRect(rect)

        for step in range(5):
            fraction = step / 4.0
            y = rect.top() + fraction * rect.height()
            grid_color = QColor("#65798a") if step == 2 else QColor("#293b4a")
            painter.setPen(QPen(grid_color, 1.2 if step == 2 else 1.0))
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
            value = value_range * (1.0 - fraction * 2.0)
            painter.setPen(QColor("#708395"))
            painter.drawText(
                QRectF(2, y - 8, rect.left() - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:g}",
            )

        for step in range(6):
            fraction = step / 5.0
            x = rect.left() + fraction * rect.width()
            painter.setPen(QPen(QColor("#243644"), 1.0))
            painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            seconds = -5.0 + fraction * 5.0
            label = "now" if step == 5 else f"{seconds:.0f}s"
            painter.setPen(QColor("#708395"))
            painter.drawText(
                QRectF(x - 18, rect.bottom() + 3, 36, 15),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        painter.setPen(QColor("#aebdca"))
        painter.drawText(rect.left(), rect.top() - 12, f"{title}  ±{value_range:g} {unit}")
        self._draw_legend(painter, rect, getter, unit)
        if len(self._history) < 2:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for IMU")
            return

        latest_timestamp_ms = self._history[-1].device_timestamp_ms
        oldest_timestamp_ms = latest_timestamp_ms - PLOT_WINDOW_MS
        painter.save()
        painter.setClipRect(rect)
        for axis, color in enumerate(AXIS_COLORS):
            painter.setPen(QPen(color, 1.6))
            previous: QPointF | None = None
            for sample in self._history:
                value = getter(sample).as_tuple()[axis]
                fraction = (sample.device_timestamp_ms - oldest_timestamp_ms) / PLOT_WINDOW_MS
                x = rect.left() + min(1.0, max(0.0, fraction)) * rect.width()
                bounded_value = min(value_range, max(-value_range, value))
                y = rect.center().y() - bounded_value / value_range * rect.height() * 0.5
                current = QPointF(x, y)
                if previous is not None:
                    painter.drawLine(QLineF(previous, current))
                previous = current
        painter.restore()

    def _draw_legend(
        self,
        painter: QPainter,
        rect: QRectF,
        getter: Callable[[IMUSample], Vector3],
        unit: str,
    ) -> None:
        values = (0.0, 0.0, 0.0)
        if self._history:
            values = getter(self._history[-1]).as_tuple()
        cell_width = 72.0
        x = rect.right() - cell_width * 3
        for name, color, value in zip(AXIS_NAMES, AXIS_COLORS, values):
            painter.setPen(color)
            painter.drawText(
                QRectF(x, rect.top() - 25, cell_width, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{name} {value:+.2f}",
            )
            x += cell_width


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
