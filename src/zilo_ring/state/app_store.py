from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from zilo_ring.domain import (
    ConnectionState,
    DetectedAction,
    IMUBatch,
    IMUSample,
    MotionEstimate,
    RingDevice,
    RingSnapshot,
)
from zilo_ring.processing import ProcessingPipeline, StreamMetrics


class LiveRecognizer(Protocol):
    @property
    def active(self) -> bool: ...

    def update(self, sample: IMUSample) -> DetectedAction | None: ...

    def reset(self) -> None: ...


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    ring: RingSnapshot
    history: tuple[IMUSample, ...]
    bias_corrected_history: tuple[IMUSample, ...]
    detected_actions: tuple[DetectedAction, ...]
    recognition_active: bool


class AppStore:
    """Thread-safe bounded state shared by the BLE worker and Qt thread."""

    def __init__(
        self,
        *,
        processor: ProcessingPipeline,
        history_size: int,
        stale_after_ms: float,
        recognizer: LiveRecognizer | None = None,
        on_detected_action: Callable[[DetectedAction], None] | None = None,
    ) -> None:
        self._processor = processor
        self._metrics = StreamMetrics()
        self._history: deque[IMUSample] = deque(maxlen=history_size)
        self._bias_corrected_history: deque[IMUSample] = deque(maxlen=history_size)
        self._detected_actions: deque[DetectedAction] = deque(maxlen=32)
        self._recognizer = recognizer
        self._on_detected_action = on_detected_action
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
                self._bias_corrected_history.append(processed.bias_corrected_sample)
                if self._recognizer is not None:
                    action = self._recognizer.update(processed.bias_corrected_sample)
                    if action is not None:
                        self._detected_actions.append(action)
                        if self._on_detected_action is not None:
                            self._on_detected_action(action)
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
            self._bias_corrected_history.clear()
            self._detected_actions.clear()
            if self._recognizer is not None:
                self._recognizer.reset()
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
            return StoreSnapshot(
                ring=ring,
                history=tuple(self._history),
                bias_corrected_history=tuple(self._bias_corrected_history),
                detected_actions=tuple(self._detected_actions),
                recognition_active=(
                    self._recognizer.active if self._recognizer is not None else False
                ),
            )
