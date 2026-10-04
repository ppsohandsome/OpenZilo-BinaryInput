from __future__ import annotations

from zilo_ring.domain import IMUSample, Vector3
from zilo_ring.recognition import DirectionTemplateModel, LiveDirectionRecognizer


def _sample(index: int, gyro: tuple[float, float, float]) -> IMUSample:
    vector = Vector3(*gyro)
    return IMUSample(
        sequence=index,
        device_timestamp_ms=index * 10,
        received_timestamp_ns=index * 10_000_000,
        accel_raw=Vector3(0.0, 0.0, 2048.0),
        gyro_raw=vector,
        accel_g=Vector3(0.0, 0.0, 1.0),
        gyro_dps=vector,
    )


def test_live_recognizer_rejects_idle_and_emits_one_completed_action() -> None:
    up = (-0.06, -0.78, 0.62)
    down = (-0.05, 0.97, -0.25)
    model = DirectionTemplateModel(templates={"up": up, "down": down})
    recognizer = LiveDirectionRecognizer(model)

    events = []
    sequence = [
        *((3.0, -4.0, 2.0) for _ in range(50)),
        *((-12.0, -156.0, 124.0) for _ in range(30)),
        *((3.0, -4.0, 2.0) for _ in range(30)),
    ]
    for index, gyro in enumerate(sequence):
        event = recognizer.update(_sample(index, gyro))
        if event is not None:
            events.append(event)

    assert len(events) == 1
    assert events[0].label == "up"
    assert events[0].similarity > 0.99
    assert events[0].start_device_timestamp_ms >= 490
    assert events[0].end_device_timestamp_ms <= 850


def test_live_recognizer_does_not_emit_for_stationary_samples() -> None:
    model = DirectionTemplateModel(
        templates={"up": (0.0, -1.0, 0.0), "down": (0.0, 1.0, 0.0)}
    )
    recognizer = LiveDirectionRecognizer(model)
    events = [
        recognizer.update(_sample(index, (5.0, -6.0, 3.0)))
        for index in range(500)
    ]
    assert all(event is None for event in events)


def test_live_recognizer_emits_rejected_diagnostic_for_incoherent_motion() -> None:
    model = DirectionTemplateModel(
        templates={"up": (0.0, -1.0, 0.0), "down": (0.0, 1.0, 0.0)}
    )
    recognizer = LiveDirectionRecognizer(model)
    events = []
    sequence = [(3.0, -4.0, 2.0) for _ in range(30)]
    for index in range(70):
        sign = 1.0 if (index // 6) % 2 == 0 else -1.0
        sequence.append((0.0, 180.0 * sign, 0.0))
    sequence.extend((3.0, -4.0, 2.0) for _ in range(20))
    for index, gyro in enumerate(sequence):
        event = recognizer.update(_sample(index, gyro))
        if event is not None:
            events.append(event)

    assert len(events) == 1
    assert events[0].label == "rejected"
    assert events[0].accepted is False
    assert events[0].rejection_reason == "direction_coherence"
    assert events[0].gyro_trace
