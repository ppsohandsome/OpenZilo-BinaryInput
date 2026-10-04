from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Public source must not contain a device-specific address. Set ZILO_RING_MAC
# locally when connecting a physical ring; an empty value selects the simulator.
DEFAULT_RING_MAC = ""
DEFAULT_CAPTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "captures"
DEFAULT_DIRECTION_MODEL_PATH = (
    Path(__file__).resolve().parents[3] / "models" / "gesture_temporal_knn.json"
)
DEFAULT_RECOGNITION_LOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "logs" / "recognition.jsonl"
)


@dataclass(frozen=True, slots=True)
class Settings:
    ring_mac: str = DEFAULT_RING_MAC
    scan_timeout_s: float = 12.0
    connect_timeout_s: float = 20.0
    sample_timeout_s: float = 3.0
    reconnect_delay_s: float = 1.5
    reconnect_max_delay_s: float = 12.0
    reconnect_jitter_ratio: float = 0.20
    ble_adapter: str = "hci0"
    ble_connect_attempts: int = 3
    # Firmware currently delivers 31-sample IMU batches roughly every 500 ms.
    # Allow one delayed batch before declaring the stream stale.
    stale_after_ms: float = 1200.0
    plot_history_samples: int = 600
    orientation_alpha: float = 0.98
    gui_refresh_hz: int = 60
    capture_dir: Path = DEFAULT_CAPTURE_DIR
    direction_model_path: Path = DEFAULT_DIRECTION_MODEL_PATH
    recognition_log_path: Path = DEFAULT_RECOGNITION_LOG_PATH

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            ring_mac=os.getenv("ZILO_RING_MAC", DEFAULT_RING_MAC).strip(),
            ble_adapter=os.getenv("ZILO_BLE_ADAPTER", "hci0").strip() or "hci0",
            capture_dir=Path(
                os.getenv("ZILO_CAPTURE_DIR", str(DEFAULT_CAPTURE_DIR))
            ).expanduser(),
            direction_model_path=Path(
                os.getenv(
                    "ZILO_DIRECTION_MODEL_PATH",
                    str(DEFAULT_DIRECTION_MODEL_PATH),
                )
            ).expanduser(),
            recognition_log_path=Path(
                os.getenv(
                    "ZILO_RECOGNITION_LOG_PATH",
                    str(DEFAULT_RECOGNITION_LOG_PATH),
                )
            ).expanduser(),
        )
