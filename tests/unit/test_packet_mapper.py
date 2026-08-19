from __future__ import annotations

from dataclasses import dataclass

import pytest

from zilo_ring.infrastructure.bluetooth.packet_mapper import map_sdk_batch, sensor_value


@dataclass
class RawSample:
    timestamp_ms: int
    accel_x: int
    accel_y: int
    accel_z: int
    gyro_x: int
    gyro_y: int
    gyro_z: int


@dataclass
class RawBatch:
    sequence_start: int
    samples: list[RawSample]


def test_sensor_value_uses_signed_full_scale() -> None:
    assert sensor_value(16384, 16.0) == pytest.approx(8.0)
    assert sensor_value(-16384, 2000.0) == pytest.approx(-1000.0)


def test_map_sdk_batch_preserves_sequence_timestamp_and_units() -> None:
    raw = RawBatch(
        sequence_start=41,
        samples=[RawSample(1200, 16384, 0, -16384, 3276, 0, -3276)],
    )
    batch = map_sdk_batch(
        raw,
        nominal_sample_rate_hz=100.0,
        accel_range_g=16.0,
        gyro_range_dps=2000.0,
    )
    sample = batch.samples[0]
    assert sample.sequence == 41
    assert sample.device_timestamp_ms == 1200
    assert sample.accel_raw.as_tuple() == (16384, 0, -16384)
    assert sample.accel_g.as_tuple() == pytest.approx((8.0, 0.0, -8.0))
    assert sample.gyro_dps.x == pytest.approx(199.951171875)
