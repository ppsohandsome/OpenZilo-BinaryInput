from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, replace

from zilo_ring.domain import (
    ConnectionState,
    IMUBatch,
    IMUSample,
    MotionEstimate,
    RingDevice,
    RingSnapshot,
)
from zilo_ring.processing import ProcessingPipeline, StreamMetrics


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    ring: RingSnapshot
    history: tuple[IMUSample, ...]


class AppStore:
    """Thread-safe bounded state shared by the BLE worker and Qt thread."""

    def __init__(
        self,
        *,
        processor: ProcessingPipeline,
        history_size: int,
        stale_after_ms: float,
    ) -> None:
        self._processor = processor
        self._metrics = StreamMetrics()
        self._history: deque[IMUSample] = deque(maxlen=history_size)
        self._ring = RingSnapshot()
        self._stale_after_ms = stale_after_ms
        self._lock = threading.Lock()

    def ingest(self, batch: IMUBatch) -> None:
        with self._lock:
            orientation = self._ring.orientation
            motion = self._ring.motion
            latest = self._ring.latest_sample
            for sample in batch.samples:
                processed = self._processor.process(sample)
                orientation = processed.orientation
                motion = processed.motion
                latest = sample
                self._metrics.update(sample)
                self._history.append(sample)
            if latest is None:
                return
            self._ring = replace(
                self._ring,
                state=ConnectionState.STREAMING,
                message="Streaming IMU",
                latest_sample=latest,
                orientation=orientation,
                motion=motion,
                receive_rate_hz=self._metrics.receive_rate_hz,
                dropped_samples=self._metrics.dropped_samples,
                nominal_sample_rate_hz=batch.nominal_sample_rate_hz,
            )

    def set_status(
        self,
        state: ConnectionState,
        message: str,
        *,
        address: str | None = None,
        reconnect_count: int | None = None,
    ) -> None:
        with self._lock:
            self._ring = replace(
                self._ring,
                state=state,
                message=message,
                address=self._ring.address if address is None else address,
                reconnect_count=(
                    self._ring.reconnect_count
                    if reconnect_count is None
                    else reconnect_count
                ),
            )

    def set_device(self, device: RingDevice) -> None:
        with self._lock:
            self._ring = replace(
                self._ring,
                address=device.address,
                battery_percent=device.battery_percent,
                nominal_sample_rate_hz=device.nominal_sample_rate_hz,
            )

    def recenter(self) -> None:
        with self._lock:
            self._processor.recenter()
            self._ring = replace(
                self._ring,
                orientation=self._processor.orientation_estimator.current(),
                motion=MotionEstimate(),
            )

    def reset_stream(self) -> None:
        with self._lock:
            self._processor.reset()
            self._metrics.reset()
            self._history.clear()
            self._ring = replace(
                self._ring,
                latest_sample=None,
                orientation=self._processor.orientation_estimator.current(),
                motion=MotionEstimate(),
                receive_rate_hz=0.0,
                dropped_samples=0,
            )

    def snapshot(self) -> StoreSnapshot:
        with self._lock:
            ring = self._ring
            if ring.latest_sample is not None:
                age_ms = (time.monotonic_ns() - ring.latest_sample.received_timestamp_ns) / 1_000_000.0
                state = ring.state
                message = ring.message
                if state == ConnectionState.STREAMING and age_ms > self._stale_after_ms:
                    state = ConnectionState.STALE
                    message = "IMU data is stale"
                ring = replace(ring, state=state, message=message, data_age_ms=max(0.0, age_ms))
            return StoreSnapshot(ring=ring, history=tuple(self._history))
