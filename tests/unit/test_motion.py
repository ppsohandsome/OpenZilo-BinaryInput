from __future__ import annotations

import pytest

from zilo_ring.domain import MotionDirection, MotionPhase, Orientation, Vector3
from zilo_ring.processing import MotionDirectionEstimator, linear_acceleration_in_control_frame


def test_gravity_is_removed_after_body_to_world_rotation() -> None:
    linear = linear_acceleration_in_control_frame(
        Vector3(-1.0, 0.0, 0.0),
        Orientation(pitch_deg=90.0),
        recenter_yaw_deg=0.0,
    )
    assert linear.x == pytest.approx(0.0, abs=1e-9)
    assert linear.y == pytest.approx(0.0, abs=1e-9)
    assert linear.z == pytest.approx(0.0, abs=1e-9)


def test_recenter_yaw_defines_the_horizontal_control_frame() -> None:
    linear = linear_acceleration_in_control_frame(
        Vector3(0.3, 0.0, 1.0),
        Orientation(yaw_deg=90.0),
        recenter_yaw_deg=90.0,
    )
    assert linear.x == pytest.approx(0.3)
    assert linear.y == pytest.approx(0.0, abs=1e-9)


def test_direction_latches_and_does_not_reverse_while_braking() -> None:
    estimator = MotionDirectionEstimator(filter_alpha=1.0)
    started = estimator.update(Vector3(0.4, 0.03, 0.0), 0)
    assert started.direction == MotionDirection.RIGHT
    assert started.phase == MotionPhase.START

    moving = estimator.update(Vector3(0.3, 0.0, 0.0), 100)
    assert moving.direction == MotionDirection.RIGHT
    assert moving.phase == MotionPhase.MOVING

    braking = estimator.update(Vector3(-0.35, 0.0, 0.0), 120)
    assert braking.direction == MotionDirection.RIGHT
    assert braking.phase == MotionPhase.BRAKING


def test_direction_returns_to_idle_after_quiet_period() -> None:
    estimator = MotionDirectionEstimator(filter_alpha=1.0, quiet_duration_ms=100)
    estimator.update(Vector3(0.3, 0.0, 0.0), 0)
    estimator.update(Vector3(0.0, 0.0, 0.0), 10)
    idle = estimator.update(Vector3(0.0, 0.0, 0.0), 120)
    assert idle.direction == MotionDirection.NONE
    assert idle.phase == MotionPhase.IDLE
