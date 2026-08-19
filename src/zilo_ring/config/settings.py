from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    ring_mac: str = ""
    sdk_path: Path | None = None
    scan_timeout_s: float = 12.0
    connect_timeout_s: float = 20.0
    sample_timeout_s: float = 3.0
    reconnect_delay_s: float = 1.5
    stale_after_ms: float = 500.0
    plot_history_samples: int = 600
    orientation_alpha: float = 0.98
    gui_refresh_hz: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        sdk_value = os.getenv("RING_SOUND_SDK_PATH", "").strip()
        return cls(
            ring_mac=os.getenv("ZILO_RING_MAC", "").strip(),
            sdk_path=Path(sdk_value).expanduser() if sdk_value else None,
        )
