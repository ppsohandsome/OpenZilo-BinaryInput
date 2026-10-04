from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DetectedAction:
    label: str
    candidate_label: str
    start_device_timestamp_ms: int
    end_device_timestamp_ms: int
    similarity: float
    direction_coherence: float
    peak_gyro_dps: float
    rejection_reason: str | None = None
    gyro_trace: tuple[tuple[int, float, float, float], ...] = ()
    accel_trace: tuple[tuple[int, float, float, float], ...] = ()
    class_scores: tuple[tuple[str, float], ...] = ()
    primary_score_name: str = "similarity"
    secondary_score_name: str = "direction_coherence"

    @property
    def accepted(self) -> bool:
        return self.rejection_reason is None

    @property
    def duration_s(self) -> float:
        return max(
            0.0,
            (self.end_device_timestamp_ms - self.start_device_timestamp_ms) / 1000.0,
        )
