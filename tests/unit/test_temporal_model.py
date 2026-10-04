from __future__ import annotations

from zilo_ring.recognition import (
    TemporalWaveformModel,
    extract_temporal_waveform,
)


def _waveform(kind: str):
    timestamps = tuple(index * 10 for index in range(180))
    gyro = [(0.0, 0.0, 0.0) for _ in timestamps]
    if kind == "single":
        for index in range(60, 70):
            gyro[index] = (0.0, 180.0, 40.0)
        for index in range(70, 80):
            gyro[index] = (0.0, -150.0, -30.0)
    elif kind == "double":
        for offset in (55, 85):
            for index in range(offset, offset + 8):
                gyro[index] = (0.0, 170.0, 35.0)
            for index in range(offset + 8, offset + 16):
                gyro[index] = (0.0, -140.0, -25.0)
    else:
        for index in range(55, 95):
            gyro[index] = (150.0, 0.0, 0.0)
    accel = tuple((0.0, 0.0, 1.0) for _ in timestamps)
    result = extract_temporal_waveform(timestamps, tuple(gyro), accel)
    assert result is not None
    return result


def test_temporal_model_round_trip_classifies_complete_waveforms(tmp_path) -> None:
    examples = [
        ("single", _waveform("single")),
        ("double", _waveform("double")),
        ("negative", _waveform("negative")),
    ]
    model = TemporalWaveformModel.fit(
        examples,
        labels=("single", "double", "negative"),
        neighbors=1,
        negative_label="negative",
    )
    assert model.predict(examples[0][1]).label == "single"
    assert model.predict(examples[1][1]).label == "double"
    assert model.predict(examples[2][1]).label == "rejected"

    path = tmp_path / "model.json"
    model.save(path, training_summary={"trials": 3})
    loaded = TemporalWaveformModel.load(path)
    assert loaded.predict(examples[1][1]).candidate_label == "double"


def test_temporal_waveform_rejects_idle_and_removes_accel_baseline() -> None:
    timestamps = tuple(index * 10 for index in range(100))
    idle_gyro = tuple((2.0, -3.0, 1.0) for _ in timestamps)
    accel = tuple((0.4, -0.2, 0.9) for _ in timestamps)
    assert extract_temporal_waveform(timestamps, idle_gyro, accel) is None
