from __future__ import annotations

import pytest

from zilo_ring.domain import IMUSample, MotionDirection, Vector3
from zilo_ring.processing import (
    IMUBiasEstimator,
    MahonyOrientationEstimator,
    ProcessingPipeline,
    StationaryDetector,
    VectorLowPassFilter,
)


def _sample(
    timestamp_ms: int,
    *,
    accel: Vector3 = Vector3(0.0, 0.0, 1.0),
    gyro: Vector3 = Vector3(0.0, 0.0, 0.0),
) -> IMUSample:
    return IMUSample(
        sequence=timestamp_ms // 10,
        device_timestamp_ms=timestamp_ms,
        received_timestamp_ns=timestamp_ms * 1_000_000,
        accel_raw=Vector3(*(value * 2048.0 for value in accel.as_tuple())),
        gyro_raw=Vector3(*(value * 16.0 for value in gyro.as_tuple())),
        accel_g=accel,
        gyro_dps=gyro,
    )


def test_stationary_detector_requires_hold_and_resets_on_motion() -> None:
    detector = StationaryDetector(hold_ms=100)
    assert not detector.update(Vector3(0.0, 0.0, 1.0), Vector3(0.0, 0.0, 0.2), 0)
    assert detector.update(Vector3(0.0, 0.0, 1.0), Vector3(0.0, 0.0, 0.2), 100)
    assert not detector.update(Vector3(0.2, 0.0, 1.0), Vector3(8.0, 0.0, 0.0), 110)
    assert not detector.update(Vector3(0.0, 0.0, 1.0), Vector3(0.0, 0.0, 0.2), 120)


def test_static_calibration_removes_gyro_bias_and_gravity_magnitude_error() -> None:
    estimator = IMUBiasEstimator(calibration_duration_ms=100, minimum_samples=5)
    result = None
    for timestamp_ms in range(0, 111, 10):
        result = estimator.update(
            Vector3(0.0, 0.0, 1.03),
            Vector3(0.8, -0.4, 1.2),
            timestamp_ms,
            stationary=True,
        )

    assert result is not None and result.calibrated
    assert result.gyro_dps.as_tuple() == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert result.accel_g.as_tuple() == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)


def test_stationary_online_tracking_follows_slow_gyro_bias_change() -> None:
    estimator = IMUBiasEstimator(
        calibration_duration_ms=100,
        minimum_samples=5,
        online_time_constant_s=1.0,
    )
    for timestamp_ms in range(0, 111, 10):
        estimator.update(
            Vector3(0.0, 0.0, 1.0),
            Vector3(0.0, 0.0, 0.0),
            timestamp_ms,
            stationary=True,
        )

    for timestamp_ms in range(120, 1121, 10):
        estimator.update(
            Vector3(0.0, 0.0, 1.0),
            Vector3(1.0, -0.5, 0.25),
            timestamp_ms,
            stationary=True,
        )

    assert estimator.gyro_bias_dps.x == pytest.approx(0.63, abs=0.02)
    assert estimator.gyro_bias_dps.y == pytest.approx(-0.315, abs=0.02)
    assert estimator.gyro_bias_dps.z == pytest.approx(0.158, abs=0.02)


def test_timestamp_aware_low_pass_reduces_alternating_noise() -> None:
    low_pass = VectorLowPassFilter(cutoff_hz=15.0)
    value = Vector3(0.0, 0.0, 0.0)
    for index in range(100):
        noisy = 1.0 if index % 2 == 0 else -1.0
        value = low_pass.update(Vector3(noisy, 0.0, 0.0), index * 10)
    assert abs(value.x) < 0.5


def test_pipeline_stays_quiet_with_static_bias_and_noise() -> None:
    pipeline = ProcessingPipeline(MahonyOrientationEstimator())
    processed = None
    for index, timestamp_ms in enumerate(range(0, 3001, 10)):
        sign = 1.0 if index % 2 == 0 else -1.0
        processed = pipeline.process(
            _sample(
                timestamp_ms,
                accel=Vector3(0.01 * sign, 0.006 * sign, 1.03),
                gyro=Vector3(0.1 * sign, -0.08 * sign, 1.2 + 0.15 * sign),
            )
        )

    assert processed is not None
    assert pipeline.bias_estimator.calibrated
    assert abs(processed.orientation.yaw_deg) < 0.1
    assert processed.linear_accel_control_g.magnitude < 0.01
    assert processed.motion.direction == MotionDirection.NONE


def test_pipeline_calibrates_large_static_gyro_bias_without_visual_drift() -> None:
    pipeline = ProcessingPipeline(MahonyOrientationEstimator())
    processed = None
    for timestamp_ms in range(0, 3001, 10):
        processed = pipeline.process(
            _sample(
                timestamp_ms,
                accel=Vector3(0.0, 0.0, 1.02),
                gyro=Vector3(31.8, -36.2, 7.45),
            )
        )

    assert processed is not None
    assert pipeline.bias_estimator.calibrated
    assert processed.orientation.roll_deg == pytest.approx(0.0, abs=0.05)
    assert processed.orientation.pitch_deg == pytest.approx(0.0, abs=0.05)
    assert processed.orientation.yaw_deg == pytest.approx(0.0, abs=0.05)
    assert processed.sample.gyro_dps.as_tuple() == pytest.approx((31.8, -36.2, 7.45))
    assert processed.bias_corrected_sample.gyro_dps.as_tuple() == pytest.approx(
        (0.0, 0.0, 0.0),
        abs=1e-9,
    )


def test_pipeline_preserves_deliberate_slow_rotation_after_bias_calibration() -> None:
    pipeline = ProcessingPipeline(
        MahonyOrientationEstimator(output_smoothing_tau_s=0.0)
    )
    for timestamp_ms in range(0, 1801, 10):
        pipeline.process(_sample(timestamp_ms, gyro=Vector3(0.0, 0.0, 1.2)))
    assert pipeline.bias_estimator.calibrated

    processed = None
    for timestamp_ms in range(1810, 2811, 10):
        processed = pipeline.process(_sample(timestamp_ms, gyro=Vector3(0.0, 0.0, 6.2)))

    assert processed is not None
    assert processed.orientation.yaw_deg == pytest.approx(5.0, abs=0.2)
