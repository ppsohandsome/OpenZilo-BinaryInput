from __future__ import annotations

import math

from zilo_ring.domain import IMUSample, Orientation


class ComplementaryOrientationEstimator:
    """Low-latency six-axis orientation with gravity-corrected roll and pitch."""

    def __init__(self, alpha: float = 0.98) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        self.alpha = alpha
        self._orientation = Orientation()
        self._last_device_timestamp_ms: int | None = None
        self._zero = Orientation()

    def update(self, sample: IMUSample) -> Orientation:
        ax, ay, az = sample.accel_g.as_tuple()
        accel_roll = math.degrees(math.atan2(ay, az))
        accel_pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))

        if self._last_device_timestamp_ms is None:
            fused = Orientation(accel_roll, accel_pitch, 0.0)
        else:
            raw_dt = (sample.device_timestamp_ms - self._last_device_timestamp_ms) / 1000.0
            dt = min(0.1, max(0.0, raw_dt))
            gyro_roll = self._orientation.roll_deg + sample.gyro_dps.x * dt
            gyro_pitch = self._orientation.pitch_deg + sample.gyro_dps.y * dt
            gyro_yaw = self._orientation.yaw_deg + sample.gyro_dps.z * dt
            fused = Orientation(
                self.alpha * gyro_roll + (1.0 - self.alpha) * accel_roll,
                self.alpha * gyro_pitch + (1.0 - self.alpha) * accel_pitch,
                _wrap_degrees(gyro_yaw),
            )

        self._last_device_timestamp_ms = sample.device_timestamp_ms
        self._orientation = fused
        return self.current()

    def current(self) -> Orientation:
        return Orientation(
            _wrap_degrees(self._orientation.roll_deg - self._zero.roll_deg),
            _wrap_degrees(self._orientation.pitch_deg - self._zero.pitch_deg),
            _wrap_degrees(self._orientation.yaw_deg - self._zero.yaw_deg),
        )

    def fused(self) -> Orientation:
        """Gravity-referenced attitude before the user display recenter offset."""
        return self._orientation

    @property
    def recenter_yaw_deg(self) -> float:
        return self._zero.yaw_deg

    def recenter(self) -> None:
        self._zero = self._orientation

    def reset(self) -> None:
        self._orientation = Orientation()
        self._zero = Orientation()
        self._last_device_timestamp_ms = None


def _wrap_degrees(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0
