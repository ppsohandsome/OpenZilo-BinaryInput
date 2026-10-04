from __future__ import annotations

import json

from zilo_ring.domain import DetectedAction
from zilo_ring.infrastructure.recognition_log import RecognitionEventLogger


def test_recognition_logger_writes_rejected_trace(tmp_path) -> None:
    path = tmp_path / "logs" / "recognition.jsonl"
    action = DetectedAction(
        label="rejected",
        candidate_label="up",
        start_device_timestamp_ms=100,
        end_device_timestamp_ms=300,
        similarity=0.91,
        direction_coherence=0.24,
        peak_gyro_dps=180.0,
        rejection_reason="direction_coherence",
        gyro_trace=((100, 1.0, 2.0, 3.0),),
        accel_trace=((100, 0.1, 0.2, 0.9),),
        class_scores=(("up", 0.91), ("down", 0.09)),
    )

    RecognitionEventLogger(path)(action)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["accepted"] is False
    assert payload["candidate_label"] == "up"
    assert payload["direction_coherence"] == 0.24
    assert payload["gyro_trace"][0]["y_dps"] == 2.0
    assert payload["accel_trace"][0]["z_g"] == 0.9
    assert payload["class_scores"]["up"] == 0.91
