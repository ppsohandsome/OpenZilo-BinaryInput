from __future__ import annotations

from dataclasses import dataclass, replace

from zilo_ring.application import RingController
from zilo_ring.capture import CaptureRecorder
from zilo_ring.config import Settings
from zilo_ring.infrastructure.bluetooth import OpenZiloRingSource
from zilo_ring.infrastructure.recognition_log import RecognitionEventLogger
from zilo_ring.infrastructure.simulation import FakeRingSource
from zilo_ring.ports import RingSource
from zilo_ring.processing import MahonyOrientationEstimator, ProcessingPipeline
from zilo_ring.recognition import load_live_recognizer
from zilo_ring.state import AppStore


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    settings: Settings
    store: AppStore
    controller: RingController
    capture_recorder: CaptureRecorder
    demo: bool


def build_application(*, demo: bool = False) -> ApplicationContext:
    settings = Settings.from_env()
    if demo:
        settings = replace(settings, ring_mac="")
    processor = ProcessingPipeline(
        MahonyOrientationEstimator()
    )
    recognizer = None
    if settings.direction_model_path.is_file():
        recognizer = load_live_recognizer(settings.direction_model_path)
    store = AppStore(
        processor=processor,
        history_size=settings.plot_history_samples,
        stale_after_ms=settings.stale_after_ms,
        recognizer=recognizer,
        on_detected_action=(
            RecognitionEventLogger(settings.recognition_log_path)
            if recognizer is not None
            else None
        ),
    )

    def source_factory(address: str) -> RingSource:
        return create_ring_source(address, settings=settings)

    controller = RingController(
        source_factory=source_factory,
        store=store,
        reconnect_delay_s=settings.reconnect_delay_s,
        reconnect_max_delay_s=settings.reconnect_max_delay_s,
        reconnect_jitter_ratio=settings.reconnect_jitter_ratio,
    )
    capture_recorder = CaptureRecorder(settings.capture_dir)
    return ApplicationContext(
        settings=settings,
        store=store,
        controller=controller,
        capture_recorder=capture_recorder,
        demo=demo,
    )


def create_ring_source(address: str, *, settings: Settings) -> RingSource:
    """Select simulation for an empty address and BLE for a physical address."""
    if not address.strip():
        return FakeRingSource()
    return OpenZiloRingSource(
        scan_timeout_s=settings.scan_timeout_s,
        connect_timeout_s=settings.connect_timeout_s,
        sample_timeout_s=settings.sample_timeout_s,
        adapter=settings.ble_adapter,
        connect_attempts=settings.ble_connect_attempts,
    )
