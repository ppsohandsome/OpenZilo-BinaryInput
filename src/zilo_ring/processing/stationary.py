from __future__ import annotations

from zilo_ring.domain import Vector3


class StationaryDetector:
    """Require both gravity-like acceleration and quiet gyro for a hold period."""

    def __init__(
        self,
        *,
        gyro_threshold_dps: float = 2.5,
        accel_tolerance_g: float = 0.10,
        hold_ms: int = 450,
    ) -> None:
        self.gyro_threshold_dps = gyro_threshold_dps
        self.accel_tolerance_g = accel_tolerance_g
        self.hold_ms = hold_ms
        self.reset()

    def update(self, accel_g: Vector3, gyro_dps: Vector3, timestamp_ms: int) -> bool:
        if self._last_timestamp_ms is not None and timestamp_ms < self._last_timestamp_ms:
            self.reset()
        self._last_timestamp_ms = timestamp_ms

        candidate = (
            gyro_dps.magnitude <= self.gyro_threshold_dps
            and abs(accel_g.magnitude - 1.0) <= self.accel_tolerance_g
        )
        if not candidate:
            self._candidate_since_ms = None
            return False
        if self._candidate_since_ms is None:
            self._candidate_since_ms = timestamp_ms
        return timestamp_ms - self._candidate_since_ms >= self.hold_ms

    def reset(self) -> None:
        self._candidate_since_ms: int | None = None
        self._last_timestamp_ms: int | None = None
