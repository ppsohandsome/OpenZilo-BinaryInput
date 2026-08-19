from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .imu_sample import Vector3


class MotionDirection(StrEnum):
    NONE = "NONE"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FORWARD = "FORWARD"
    BACK = "BACK"
    UP = "UP"
    DOWN = "DOWN"


class MotionPhase(StrEnum):
    IDLE = "IDLE"
    START = "START"
    MOVING = "MOVING"
    BRAKING = "BRAKING"


@dataclass(frozen=True, slots=True)
class MotionEstimate:
    direction: MotionDirection = MotionDirection.NONE
    phase: MotionPhase = MotionPhase.IDLE
    direction_vector: Vector3 = Vector3(0.0, 0.0, 0.0)
    linear_accel_control_g: Vector3 = Vector3(0.0, 0.0, 0.0)
    intensity_g: float = 0.0
    confidence: float = 0.0
