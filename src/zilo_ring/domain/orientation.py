from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Orientation:
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
