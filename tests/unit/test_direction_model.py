from __future__ import annotations

from zilo_ring.recognition import (
    DirectionTemplateModel,
    extract_trial_features,
)


def test_activity_gate_rejects_stationary_data_and_short_spike() -> None:
    timestamps = tuple(index * 10 for index in range(100))
    stationary = tuple((3.0, -4.0, 2.0) for _ in timestamps)
    assert extract_trial_features(timestamps, stationary) is None

    short_spike = list(stationary)
    for index in range(40, 44):
        short_spike[index] = (0.0, 100.0, 0.0)
    assert extract_trial_features(timestamps, tuple(short_spike)) is None

    sustained_small_motion = list(stationary)
    for index in range(30, 60):
        sustained_small_motion[index] = (0.0, 60.0, 0.0)
    assert extract_trial_features(timestamps, tuple(sustained_small_motion)) is None


def test_direction_templates_classify_actions_and_keep_idle() -> None:
    timestamps = tuple(index * 10 for index in range(100))

    def gesture(y: float, z: float):
        values = [(2.0, -3.0, 1.0) for _ in timestamps]
        for index in range(30, 60):
            values[index] = (0.0, y, z)
        return extract_trial_features(timestamps, tuple(values))

    up = gesture(-160.0, 120.0)
    down = gesture(180.0, -50.0)
    assert up is not None
    assert down is not None
    model = DirectionTemplateModel.fit((("up", up), ("down", down)))

    assert model.predict_features(up) == "up"
    assert model.predict_features(down) == "down"
    assert model.predict_features(None) == "idle"


def test_direction_model_rejects_incoherent_strong_motion() -> None:
    timestamps = tuple(index * 10 for index in range(120))
    values = [(2.0, -3.0, 1.0) for _ in timestamps]
    for index in range(20, 90):
        sign = 1.0 if (index // 5) % 2 == 0 else -1.0
        values[index] = (0.0, -180.0 * sign, 130.0 * sign)
    features = extract_trial_features(timestamps, tuple(values))
    assert features is not None
    model = DirectionTemplateModel(
        templates={
            "up": (-0.06, -0.78, 0.62),
            "down": (-0.05, 0.97, -0.25),
        }
    )
    assert features.direction_coherence < model.min_direction_coherence
    assert model.predict_features(features) == "rejected"
