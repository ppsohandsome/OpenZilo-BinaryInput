from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from zilo_ring.domain import DetectedAction


class RecognitionEventLogger:
    """Append completed recognition attempts as durable JSON Lines records."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __call__(self, action: DetectedAction) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "label": action.label,
            "candidate_label": action.candidate_label,
            "accepted": action.accepted,
            "rejection_reason": action.rejection_reason,
            "start_device_timestamp_ms": action.start_device_timestamp_ms,
            "end_device_timestamp_ms": action.end_device_timestamp_ms,
            "duration_s": action.duration_s,
            "similarity": action.similarity,
            "direction_coherence": action.direction_coherence,
            "primary_score_name": action.primary_score_name,
            "secondary_score_name": action.secondary_score_name,
            "class_scores": dict(action.class_scores),
            "peak_gyro_dps": action.peak_gyro_dps,
            "gyro_trace": [
                {
                    "device_timestamp_ms": timestamp_ms,
                    "x_dps": x,
                    "y_dps": y,
                    "z_dps": z,
                }
                for timestamp_ms, x, y, z in action.gyro_trace
            ],
            "accel_trace": [
                {
                    "device_timestamp_ms": timestamp_ms,
                    "x_g": x,
                    "y_g": y,
                    "z_g": z,
                }
                for timestamp_ms, x, y, z in action.accel_trace
            ],
        }
        with self.path.open("a", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
