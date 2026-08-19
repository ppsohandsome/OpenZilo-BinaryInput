from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vector3:
    x: float
    y: float
    z: float

    def as_tuple(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z

    @property
    def magnitude(self) -> float:
        return (self.x * self.x + self.y * self.y + self.z * self.z) ** 0.5


@dataclass(frozen=True, slots=True)
class IMUSample:
    sequence: int
    device_timestamp_ms: int
    received_timestamp_ns: int
    accel_raw: Vector3
    gyro_raw: Vector3
    accel_g: Vector3
    gyro_dps: Vector3


@dataclass(frozen=True, slots=True)
class IMUBatch:
    samples: tuple[IMUSample, ...]
    nominal_sample_rate_hz: float
    accel_range_g: float | None
    gyro_range_dps: float | None
