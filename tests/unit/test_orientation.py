from __future__ import annotations

import pytest

from zilo_ring.domain import IMUSample, Vector3
from zilo_ring.processing import (
    ComplementaryOrientationEstimator,
    MahonyOrientationEstimator,
)


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


def test_mahony_initializes_roll_and_pitch_from_gravity() -> None:
    estimator = MahonyOrientationEstimator(output_smoothing_tau_s=0.0)
    tilted = _sample_with_vectors(0, accel=Vector3(0.0, 1.0, 0.0))

    orientation = estimator.update(tilted)

    assert orientation.roll_deg == pytest.approx(90.0)
    assert orientation.pitch_deg == pytest.approx(0.0)


def test_mahony_integrates_yaw_and_recenter_uses_quaternion_reference() -> None:
    estimator = MahonyOrientationEstimator(output_smoothing_tau_s=0.0)
    estimator.update(sample(0))
    for timestamp_ms in range(10, 1010, 10):
        orientation = estimator.update(sample(timestamp_ms, gyro_z=10.0))

    assert orientation.yaw_deg == pytest.approx(10.0, abs=0.02)
    assert estimator.fused().yaw_deg == pytest.approx(10.0, abs=0.02)

    estimator.recenter()
    assert estimator.current().yaw_deg == pytest.approx(0.0, abs=1e-9)
    assert estimator.recenter_yaw_deg == pytest.approx(10.0, abs=0.02)


def test_mahony_rejects_acceleration_magnitude_far_from_gravity() -> None:
    estimator = MahonyOrientationEstimator(
        kp=8.0,
        accel_rejection_g=0.1,
        output_smoothing_tau_s=0.0,
    )
    estimator.update(sample(0))
    for timestamp_ms in range(10, 1010, 10):
        orientation = estimator.update(
            _sample_with_vectors(timestamp_ms, accel=Vector3(1.0, 0.0, 1.0))
        )

    assert orientation.roll_deg == pytest.approx(0.0, abs=1e-9)
    assert orientation.pitch_deg == pytest.approx(0.0, abs=1e-9)


def test_mahony_smooths_the_output_quaternion_not_the_fusion_state() -> None:
    estimator = MahonyOrientationEstimator(
        kp=0.0,
        output_smoothing_tau_s=0.1,
    )
    estimator.update(sample(0))

    displayed = estimator.update(sample(50, gyro_z=90.0))
    fused = estimator.fused()

    assert 0.0 < displayed.yaw_deg < fused.yaw_deg
    assert fused.yaw_deg == pytest.approx(4.5, abs=0.01)


def _sample_with_vectors(
    timestamp_ms: int,
    *,
    accel: Vector3 = Vector3(0.0, 0.0, 1.0),
    gyro: Vector3 = Vector3(0.0, 0.0, 0.0),
) -> IMUSample:
    return IMUSample(
        sequence=timestamp_ms // 10,
        device_timestamp_ms=timestamp_ms,
        received_timestamp_ns=timestamp_ms * 1_000_000,
        accel_raw=accel,
        gyro_raw=gyro,
        accel_g=accel,
        gyro_dps=gyro,
    )
