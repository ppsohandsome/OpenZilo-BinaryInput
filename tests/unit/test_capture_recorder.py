from __future__ import annotations

import csv
import json

import pytest

from zilo_ring.capture import CaptureRecorder
from zilo_ring.capture.recorder import (
    CAPTURE_HAND_ANGLES_DEG,
    CAPTURE_LABEL_DISPLAY,
    CAPTURE_LABELS,
)


def test_capture_labels_include_complete_gestures() -> None:
    assert "single_press_rebound" in CAPTURE_LABELS
    assert "up_flick_rebound" in CAPTURE_LABELS
    assert "double_press_rebound" in CAPTURE_LABELS
    assert "gesture_negative_v2" in CAPTURE_LABELS
    assert "desk_tap_return" not in CAPTURE_LABELS
    assert CAPTURE_LABEL_DISPLAY["single_press_rebound"] == "单次按压回弹"
    assert CAPTURE_HAND_ANGLES_DEG == (0, 10, 20, -10, -20)
from zilo_ring.domain import IMUSample, Vector3


def _sample(sequence: int, *, bias: bool = False) -> IMUSample:
    timestamp_ms = sequence * 10
    offset = 1.0 if bias else 10.0
    return IMUSample(
        sequence=sequence,
        device_timestamp_ms=timestamp_ms,
        received_timestamp_ns=1_000_000_000 + timestamp_ms * 1_000_000,
        accel_raw=Vector3(100, 200, 300),
        gyro_raw=Vector3(400, 500, 600),
        accel_g=Vector3(offset, offset + 1.0, offset + 2.0),
        gyro_dps=Vector3(offset + 3.0, offset + 4.0, offset + 5.0),
    )


def test_capture_recorder_saves_aligned_deduplicated_csv_and_metadata(tmp_path) -> None:
    recorder = CaptureRecorder(tmp_path)
    raw = tuple(_sample(index) for index in range(3))
    bias = tuple(_sample(index, bias=True) for index in range(3))

    recorder.start(
        label="left",
        speed="normal",
        amplitude="large",
        hand_angle_deg=-20,
        notes="fixed wear mark",
    )
    recorder.ingest(raw, bias)
    recorder.ingest(raw, bias)
    path = recorder.stop()

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["label"] == "left"
    assert rows[0]["amplitude"] == "large"
    assert int(rows[0]["hand_angle_deg"]) == -20
    assert rows[0]["negative_type"] == "not_applicable"
    assert float(rows[0]["accel_raw_g_x"]) == pytest.approx(10.0)
    assert float(rows[0]["accel_bias_g_x"]) == pytest.approx(1.0)
    assert float(rows[-1]["elapsed_ms"]) == pytest.approx(20.0)

    metadata_path = path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["sample_count"] == 3
    assert metadata["notes"] == "fixed wear mark"
    assert metadata["amplitude"] == "large"
    assert metadata["hand_angle_deg"] == -20
    assert metadata["negative_type"] == "not_applicable"
    assert metadata["wear_mode"] == "fixed"
    assert metadata["value_order"] == "raw/bias"


def test_capture_recorder_rejects_stop_without_samples(tmp_path) -> None:
    recorder = CaptureRecorder(tmp_path)
    recorder.start(label="up", speed="slow")

    with pytest.raises(RuntimeError, match="No aligned IMU samples"):
        recorder.stop()

    assert not recorder.status.recording


def test_capture_recorder_retake_discards_only_the_unsaved_take(tmp_path) -> None:
    recorder = CaptureRecorder(tmp_path)
    first_raw = tuple(_sample(index) for index in range(3))
    first_bias = tuple(_sample(index, bias=True) for index in range(3))
    recorder.start(
        label="gesture_negative_v2",
        speed="fast",
        amplitude="small",
        hand_angle_deg=20,
        negative_type="natural_tremor",
        notes="same metadata",
    )
    recorder.ingest(first_raw, first_bias)

    recorder.restart(exclude_through_received_ns=first_raw[-1].received_timestamp_ns)
    assert recorder.status.recording
    assert recorder.status.sample_count == 0
    assert recorder.status.label == "gesture_negative_v2"
    assert recorder.status.speed == "fast"
    assert recorder.status.amplitude == "small"
    assert recorder.status.hand_angle_deg == 20
    assert recorder.status.negative_type == "natural_tremor"

    second_raw = tuple(_sample(index) for index in range(3, 6))
    second_bias = tuple(_sample(index, bias=True) for index in range(3, 6))
    recorder.ingest(first_raw + second_raw, first_bias + second_bias)
    path = recorder.stop()

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["sequence"]) for row in rows] == [3, 4, 5]
    metadata = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert metadata["notes"] == "same metadata"


def test_capture_recorder_validates_negative_type_and_angle(tmp_path) -> None:
    recorder = CaptureRecorder(tmp_path)

    with pytest.raises(ValueError, match="Unsupported hand angle"):
        recorder.start(label="up", speed="normal", hand_angle_deg=30)

    with pytest.raises(ValueError, match="Unsupported negative type"):
        recorder.start(label="gesture_negative_v2", speed="normal")

    with pytest.raises(ValueError, match="only valid for negative"):
        recorder.start(
            label="up",
            speed="normal",
            negative_type="stationary",
        )
