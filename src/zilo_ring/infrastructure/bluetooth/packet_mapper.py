from __future__ import annotations

import time
from typing import Any

from zilo_ring.domain import IMUBatch, IMUSample, Vector3


def sensor_value(raw: int, value_range: float | None) -> float:
    if not value_range:
        return float(raw)
    return float(raw) / 32768.0 * float(value_range)


def map_sdk_batch(
    raw_batch: Any,
    *,
    nominal_sample_rate_hz: float,
    accel_range_g: float | None,
    gyro_range_dps: float | None,
) -> IMUBatch:
    sequence_start = int(raw_batch.sequence_start)
    received_ns = time.monotonic_ns()
    samples = tuple(
        _map_sample(
            raw,
            sequence=sequence_start + offset,
            received_ns=received_ns,
            accel_range_g=accel_range_g,
            gyro_range_dps=gyro_range_dps,
        )
        for offset, raw in enumerate(raw_batch.samples)
    )
    return IMUBatch(
        samples=samples,
        nominal_sample_rate_hz=nominal_sample_rate_hz,
        accel_range_g=accel_range_g,
        gyro_range_dps=gyro_range_dps,
    )


def _map_sample(
    raw: Any,
    *,
    sequence: int,
    received_ns: int,
    accel_range_g: float | None,
    gyro_range_dps: float | None,
) -> IMUSample:
    accel_raw = Vector3(int(raw.accel_x), int(raw.accel_y), int(raw.accel_z))
    gyro_raw = Vector3(int(raw.gyro_x), int(raw.gyro_y), int(raw.gyro_z))
    accel_g = Vector3(*(sensor_value(int(value), accel_range_g) for value in accel_raw.as_tuple()))
    gyro_dps = Vector3(*(sensor_value(int(value), gyro_range_dps) for value in gyro_raw.as_tuple()))
    return IMUSample(
        sequence=sequence,
        device_timestamp_ms=int(raw.timestamp_ms),
        received_timestamp_ns=received_ns,
        accel_raw=accel_raw,
        gyro_raw=gyro_raw,
        accel_g=accel_g,
        gyro_dps=gyro_dps,
    )
