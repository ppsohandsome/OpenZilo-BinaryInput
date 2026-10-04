from __future__ import annotations

from zilo_ring.domain import IMUSample, Vector3
from zilo_ring.recognition import (
    LiveTemporalGestureRecognizer,
    TemporalPrediction,
    TemporalWaveform,
)


class _Model:
    activity_threshold_dps = 20.0
    before_peak_s = 0.45
    negative_label = "negative"
    rejected_label = "rejected"

    def extract(self, timestamps, gyro, accel):
        return TemporalWaveform(
            values=(1.0,),
            active_start_s=0.45,
            active_end_s=0.65,
            peak_gyro_dps=180.0,
        )

    def predict(self, waveform):
        return TemporalPrediction(
            label="single",
            candidate_label="single",
            confidence=0.9,
            vote_margin=0.8,
            nearest_distance=0.1,
            scores={"single": 0.9, "negative": 0.1},
            rejection_reason=None,
        )


def _sample(index: int, gyro_y: float) -> IMUSample:
    return IMUSample(
        sequence=index,
        device_timestamp_ms=index * 10,
        received_timestamp_ns=index * 10_000_000,
        accel_raw=Vector3(0.0, 0.0, 0.0),
        gyro_raw=Vector3(0.0, 0.0, 0.0),
        accel_g=Vector3(0.0, 0.0, 1.0),
        gyro_dps=Vector3(0.0, gyro_y, 0.0),
    )


def test_live_temporal_recognizer_uses_short_quiet_period() -> None:
    recognizer = LiveTemporalGestureRecognizer(_Model())  # type: ignore[arg-type]
    events = []
    values = [0.0] * 30 + [180.0] * 20 + [0.0] * 30
    for index, value in enumerate(values):
        event = recognizer.update(_sample(index, value))
        if event is not None:
            events.append(event)

    assert len(events) == 1
    assert events[0].label == "single"
    assert events[0].primary_score_name == "confidence"
    assert events[0].start_device_timestamp_ms == 450
    assert events[0].end_device_timestamp_ms == 650
