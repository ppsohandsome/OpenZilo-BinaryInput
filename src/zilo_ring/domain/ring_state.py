from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .imu_sample import IMUSample
from .motion import MotionEstimate
from .orientation import Orientation


class ConnectionState(StrEnum):
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    STALE = "stale"
    RECONNECTING = "reconnecting"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RingDevice:
    address: str
    name: str = "OpenZilo Ring"
    battery_percent: int | None = None
    nominal_sample_rate_hz: float | None = None


@dataclass(frozen=True, slots=True)
class RingSnapshot:
    state: ConnectionState = ConnectionState.IDLE
    message: str = "Not connected"
    address: str = ""
    latest_sample: IMUSample | None = None
    orientation: Orientation = Orientation()
    motion: MotionEstimate = MotionEstimate()
    receive_rate_hz: float = 0.0
    data_age_ms: float | None = None
    dropped_samples: int = 0
    reconnect_count: int = 0
    battery_percent: int | None = None
    nominal_sample_rate_hz: float | None = None
