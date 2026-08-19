from __future__ import annotations

import math

from zilo_ring.domain import (
    MotionDirection,
    MotionEstimate,
    MotionPhase,
    Orientation,
    Vector3,
)


class MotionDirectionEstimator:
    """Short gesture direction estimate; deliberately does not integrate position."""

    def __init__(
        self,
        *,
        filter_alpha: float = 0.30,
        start_threshold_g: float = 0.12,
        stop_threshold_g: float = 0.055,
        quiet_duration_ms: int = 140,
        start_hold_ms: int = 90,
    ) -> None:
        self.filter_alpha = filter_alpha
        self.start_threshold_g = start_threshold_g
        self.stop_threshold_g = stop_threshold_g
        self.quiet_duration_ms = quiet_duration_ms
        self.start_hold_ms = start_hold_ms
        self.reset()

    def update(self, linear_accel_control_g: Vector3, timestamp_ms: int) -> MotionEstimate:
        self._filtered = _blend(self._filtered, linear_accel_control_g, self.filter_alpha)
        magnitude = self._filtered.magnitude

        if not self._active:
            if magnitude < self.start_threshold_g:
                return self._idle_estimate()
            self._active = True
            self._started_ms = timestamp_ms
            self._quiet_since_ms = None
            self._direction_vector = _normalized(self._filtered)
            self._direction = _dominant_direction(self._direction_vector)
            self._confidence = _direction_confidence(self._direction_vector)
            phase = MotionPhase.START
        else:
            if magnitude < self.stop_threshold_g:
                if self._quiet_since_ms is None:
                    self._quiet_since_ms = timestamp_ms
                elif timestamp_ms - self._quiet_since_ms >= self.quiet_duration_ms:
                    self._clear_gesture()
                    return self._idle_estimate()
            else:
                self._quiet_since_ms = None

            projection = _dot(self._filtered, self._direction_vector)
            if projection < -self.stop_threshold_g:
                phase = MotionPhase.BRAKING
            elif timestamp_ms - self._started_ms < self.start_hold_ms:
                phase = MotionPhase.START
            else:
                phase = MotionPhase.MOVING

        return MotionEstimate(
            direction=self._direction,
            phase=phase,
            direction_vector=self._direction_vector,
            linear_accel_control_g=self._filtered,
            intensity_g=magnitude,
            confidence=self._confidence,
        )

    def reset(self) -> None:
        self._filtered = Vector3(0.0, 0.0, 0.0)
        self._clear_gesture()

    def _clear_gesture(self) -> None:
        self._active = False
        self._started_ms = 0
        self._quiet_since_ms: int | None = None
        self._direction_vector = Vector3(0.0, 0.0, 0.0)
        self._direction = MotionDirection.NONE
        self._confidence = 0.0

    def _idle_estimate(self) -> MotionEstimate:
        return MotionEstimate(
            linear_accel_control_g=self._filtered,
            intensity_g=self._filtered.magnitude,
        )


def linear_acceleration_in_control_frame(
    accel_body_g: Vector3,
    fused_orientation: Orientation,
    recenter_yaw_deg: float,
) -> Vector3:
    """Rotate body acceleration to a Z-up control frame and remove 1 g gravity."""
    world = _rotate_zyx(accel_body_g, fused_orientation)
    gravity_removed = Vector3(world.x, world.y, world.z - 1.0)
    yaw = math.radians(-recenter_yaw_deg)
    cosine, sine = math.cos(yaw), math.sin(yaw)
    return Vector3(
        cosine * gravity_removed.x - sine * gravity_removed.y,
        sine * gravity_removed.x + cosine * gravity_removed.y,
        gravity_removed.z,
    )


def _rotate_zyx(vector: Vector3, orientation: Orientation) -> Vector3:
    roll, pitch, yaw = (
        math.radians(orientation.roll_deg),
        math.radians(orientation.pitch_deg),
        math.radians(orientation.yaw_deg),
    )
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, y, z = vector.as_tuple()
    return Vector3(
        (cy * cp) * x + (cy * sp * sr - sy * cr) * y + (cy * sp * cr + sy * sr) * z,
        (sy * cp) * x + (sy * sp * sr + cy * cr) * y + (sy * sp * cr - cy * sr) * z,
        (-sp) * x + (cp * sr) * y + (cp * cr) * z,
    )


def _blend(previous: Vector3, current: Vector3, alpha: float) -> Vector3:
    inverse = 1.0 - alpha
    return Vector3(
        previous.x * inverse + current.x * alpha,
        previous.y * inverse + current.y * alpha,
        previous.z * inverse + current.z * alpha,
    )


def _normalized(vector: Vector3) -> Vector3:
    magnitude = vector.magnitude
    if magnitude <= 1e-9:
        return Vector3(0.0, 0.0, 0.0)
    return Vector3(vector.x / magnitude, vector.y / magnitude, vector.z / magnitude)


def _dot(left: Vector3, right: Vector3) -> float:
    return left.x * right.x + left.y * right.y + left.z * right.z


def _dominant_direction(vector: Vector3) -> MotionDirection:
    components = (abs(vector.x), abs(vector.y), abs(vector.z))
    axis = components.index(max(components))
    if axis == 0:
        return MotionDirection.RIGHT if vector.x >= 0 else MotionDirection.LEFT
    if axis == 1:
        return MotionDirection.FORWARD if vector.y >= 0 else MotionDirection.BACK
    return MotionDirection.UP if vector.z >= 0 else MotionDirection.DOWN


def _direction_confidence(vector: Vector3) -> float:
    absolute = tuple(abs(value) for value in vector.as_tuple())
    total = sum(absolute)
    if total <= 1e-9:
        return 0.0
    dominance = max(absolute) / total
    return min(1.0, max(0.0, (dominance - 1.0 / 3.0) * 1.5))
