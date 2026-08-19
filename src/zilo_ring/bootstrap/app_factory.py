from __future__ import annotations

from dataclasses import dataclass

from zilo_ring.application import RingController
from zilo_ring.config import Settings
from zilo_ring.infrastructure.bluetooth import AdvxRingSource
from zilo_ring.infrastructure.simulation import FakeRingSource
from zilo_ring.processing import ComplementaryOrientationEstimator, ProcessingPipeline
from zilo_ring.state import AppStore


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    settings: Settings
    store: AppStore
    controller: RingController
    demo: bool


def build_application(*, demo: bool = False) -> ApplicationContext:
    settings = Settings.from_env()
    processor = ProcessingPipeline(
        ComplementaryOrientationEstimator(alpha=settings.orientation_alpha)
    )
    store = AppStore(
        processor=processor,
        history_size=settings.plot_history_samples,
        stale_after_ms=settings.stale_after_ms,
    )

    if demo:
        source_factory = FakeRingSource
    else:
        source_factory = lambda: AdvxRingSource(
            sdk_path=settings.sdk_path,
            scan_timeout_s=settings.scan_timeout_s,
            connect_timeout_s=settings.connect_timeout_s,
            sample_timeout_s=settings.sample_timeout_s,
        )

    controller = RingController(
        source_factory=source_factory,
        store=store,
        reconnect_delay_s=settings.reconnect_delay_s,
    )
    return ApplicationContext(
        settings=settings,
        store=store,
        controller=controller,
        demo=demo,
    )
