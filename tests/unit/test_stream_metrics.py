from __future__ import annotations

import pytest

from zilo_ring.domain import IMUSample, Vector3
from zilo_ring.processing import StreamMetrics


def make_sample(sequence: int, timestamp_ms: int) -> IMUSample:
    zero = Vector3(0, 0, 0)
    return IMUSample(
        sequence=sequence,
        device_timestamp_ms=timestamp_ms,
        received_timestamp_ns=timestamp_ms * 1_000_000,
        accel_raw=zero,
        gyro_raw=zero,
        accel_g=zero,
        gyro_dps=zero,
    )


def test_rate_uses_device_samples_not_batch_delivery_cadence() -> None:
    metrics = StreamMetrics()
    for sequence in range(101):
        metrics.update(make_sample(sequence, sequence * 10))
    assert metrics.receive_rate_hz == pytest.approx(100.0)


def test_sequence_gaps_are_counted() -> None:
    metrics = StreamMetrics()
    metrics.update(make_sample(10, 100))
    metrics.update(make_sample(13, 130))
    assert metrics.dropped_samples == 2
