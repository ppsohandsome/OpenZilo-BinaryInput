from __future__ import annotations

import pytest

from zilo_ring.domain import IMUSample, Vector3
from zilo_ring.processing import ComplementaryOrientationEstimator


def sample(timestamp_ms: int, *, gyro_z: float = 0.0) -> IMUSample:
    return IMUSample(
        sequence=timestamp_ms // 10,
        device_timestamp_ms=timestamp_ms,
        received_timestamp_ns=timestamp_ms * 1_000_000,
        accel_raw=Vector3(0, 0, 2048),
        gyro_raw=Vector3(0, 0, gyro_z),
        accel_g=Vector3(0, 0, 1),
        gyro_dps=Vector3(0, 0, gyro_z),
    )


def test_level_sample_starts_at_zero_roll_and_pitch() -> None:
    estimator = ComplementaryOrientationEstimator()
    orientation = estimator.update(sample(0))
    assert orientation.roll_deg == pytest.approx(0.0)
    assert orientation.pitch_deg == pytest.approx(0.0)


def test_yaw_integrates_gyro_and_recenter_sets_relative_zero() -> None:
    estimator = ComplementaryOrientationEstimator()
    estimator.update(sample(0))
    orientation = estimator.update(sample(100, gyro_z=90.0))
    assert orientation.yaw_deg == pytest.approx(9.0)
    estimator.recenter()
    assert estimator.current().yaw_deg == pytest.approx(0.0)
