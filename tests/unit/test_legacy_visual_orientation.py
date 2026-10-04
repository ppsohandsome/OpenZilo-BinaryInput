from __future__ import annotations

import pytest

from zilo_ring.domain import Vector3
from zilo_ring.processing import LegacyVisualOrientationEstimator


def test_legacy_visualizer_calibrates_static_bias_and_freezes_small_motion() -> None:
    estimator = LegacyVisualOrientationEstimator(
        calibration_duration_ms=100,
        visual_delay_ms=0,
    )
    bias = Vector3(31.8, -36.2, 7.45)
    for timestamp_ms in range(0, 111, 10):
        orientation = estimator.update(Vector3(0.99, 0.0, 0.04), bias, timestamp_ms)

    assert estimator.calibrated
    assert estimator.gyro_bias_dps.as_tuple() == pytest.approx(bias.as_tuple())
    for timestamp_ms in range(120, 1121, 10):
        orientation = estimator.update(
            Vector3(0.99, 0.0, 0.04),
            Vector3(bias.x + 8.0, bias.y, bias.z),
            timestamp_ms,
        )

    assert orientation.roll_deg == pytest.approx(0.0, abs=1e-9)
    assert orientation.pitch_deg == pytest.approx(0.0, abs=1e-9)
    assert orientation.yaw_deg == pytest.approx(0.0, abs=1e-9)


def test_legacy_visualizer_reacts_to_change_above_stationary_deadzone() -> None:
    estimator = LegacyVisualOrientationEstimator(
        calibration_duration_ms=0,
        visual_delay_ms=0,
    )
    gravity = Vector3(0.0, 0.0, 1.0)
    estimator.update(gravity, Vector3(0.0, 0.0, 0.0), 0)
    estimator.update(gravity, Vector3(40.0, 0.0, 0.0), 10)
    orientation = estimator.update(gravity, Vector3(80.0, 0.0, 0.0), 20)

    assert orientation.roll_deg > 0.0
    assert orientation.pitch_deg == pytest.approx(0.0, abs=1e-9)
    assert orientation.yaw_deg == pytest.approx(0.0, abs=1e-9)


def test_legacy_visualizer_holds_back_seventy_milliseconds() -> None:
    estimator = LegacyVisualOrientationEstimator(
        calibration_duration_ms=0,
        visual_delay_ms=70,
    )
    gravity = Vector3(0.0, 0.0, 1.0)
    estimator.update(gravity, Vector3(0.0, 0.0, 0.0), 0)
    estimator.update(gravity, Vector3(40.0, 0.0, 0.0), 10)
    orientation = estimator.update(gravity, Vector3(80.0, 0.0, 0.0), 20)

    assert orientation.roll_deg == pytest.approx(0.0)
