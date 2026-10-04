from __future__ import annotations

import math

from zilo_ring.domain import Vector3


class VectorLowPassFilter:
    """Timestamp-aware first-order low-pass filter for a three-axis signal."""

    def __init__(self, cutoff_hz: float) -> None:
        if cutoff_hz <= 0.0:
            raise ValueError("cutoff_hz must be positive")
        self.cutoff_hz = cutoff_hz
        self.reset()

    def update(self, value: Vector3, timestamp_ms: int) -> Vector3:
        if self._value is None or self._timestamp_ms is None:
            self._value = value
            self._timestamp_ms = timestamp_ms
            return value

        dt = (timestamp_ms - self._timestamp_ms) / 1000.0
        self._timestamp_ms = timestamp_ms
        if dt <= 0.0:
            return self._value

        # Computing alpha from dt keeps the cutoff stable if packets are uneven.
        alpha = 1.0 - math.exp(-2.0 * math.pi * self.cutoff_hz * min(dt, 0.1))
        self._value = blend(self._value, value, alpha)
        return self._value

    def reset(self) -> None:
        self._value: Vector3 | None = None
        self._timestamp_ms: int | None = None


def blend(previous: Vector3, current: Vector3, alpha: float) -> Vector3:
    inverse = 1.0 - alpha
    return Vector3(
        previous.x * inverse + current.x * alpha,
        previous.y * inverse + current.y * alpha,
        previous.z * inverse + current.z * alpha,
    )
