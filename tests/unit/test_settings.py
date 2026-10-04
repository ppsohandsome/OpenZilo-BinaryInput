from __future__ import annotations

from zilo_ring.config import (
    DEFAULT_CAPTURE_DIR,
    DEFAULT_DIRECTION_MODEL_PATH,
    DEFAULT_RECOGNITION_LOG_PATH,
    DEFAULT_RING_MAC,
    Settings,
)


def test_default_ring_mac_has_one_source(monkeypatch) -> None:
    monkeypatch.delenv("ZILO_RING_MAC", raising=False)

    assert Settings().ring_mac == DEFAULT_RING_MAC
    assert Settings.from_env().ring_mac == DEFAULT_RING_MAC
    assert DEFAULT_RING_MAC == ""
    assert Settings().stale_after_ms == 1200.0


def test_ring_mac_can_be_overridden_for_one_run(monkeypatch) -> None:
    monkeypatch.setenv("ZILO_RING_MAC", "AA:BB:CC:DD:EE:FF")

    assert Settings.from_env().ring_mac == "AA:BB:CC:DD:EE:FF"


def test_capture_directory_is_stable_and_can_be_overridden(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZILO_CAPTURE_DIR", raising=False)
    assert Settings.from_env().capture_dir == DEFAULT_CAPTURE_DIR

    custom = tmp_path / "captures"
    monkeypatch.setenv("ZILO_CAPTURE_DIR", str(custom))
    assert Settings.from_env().capture_dir == custom


def test_direction_model_path_is_stable_and_can_be_overridden(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZILO_DIRECTION_MODEL_PATH", raising=False)
    assert Settings.from_env().direction_model_path == DEFAULT_DIRECTION_MODEL_PATH

    custom = tmp_path / "direction.json"
    monkeypatch.setenv("ZILO_DIRECTION_MODEL_PATH", str(custom))
    assert Settings.from_env().direction_model_path == custom


def test_recognition_log_path_is_stable_and_can_be_overridden(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZILO_RECOGNITION_LOG_PATH", raising=False)
    assert Settings.from_env().recognition_log_path == DEFAULT_RECOGNITION_LOG_PATH

    custom = tmp_path / "recognition.jsonl"
    monkeypatch.setenv("ZILO_RECOGNITION_LOG_PATH", str(custom))
    assert Settings.from_env().recognition_log_path == custom
