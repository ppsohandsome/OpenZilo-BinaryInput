from __future__ import annotations

from zilo_ring.domain import IMUSample, Vector3
from zilo_ring.presentation.qt.pages.visualization.sensor_charts import _windowed_history


def _sample(timestamp_ms: int) -> IMUSample:
    zero = Vector3(0, 0, 0)
    return IMUSample(
        sequence=timestamp_ms // 1000,
        device_timestamp_ms=timestamp_ms,
        received_timestamp_ns=timestamp_ms * 1_000_000,
        accel_raw=zero,
        gyro_raw=zero,
        accel_g=zero,
        gyro_dps=zero,
    )


def test_history_window_is_time_based() -> None:
    history = tuple(_sample(timestamp_ms) for timestamp_ms in range(0, 11_000, 1_000))
    windowed = _windowed_history(history, 5_000)
    assert [sample.device_timestamp_ms for sample in windowed] == [
        5_000,
        6_000,
        7_000,
        8_000,
        9_000,
        10_000,
    ]
