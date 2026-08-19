from __future__ import annotations

from collections import deque

from zilo_ring.domain import IMUSample


class StreamMetrics:
    def __init__(self, window_samples: int = 300) -> None:
        self._points: deque[tuple[int, int]] = deque(maxlen=window_samples)
        self._last_sequence: int | None = None
        self.dropped_samples = 0

    def update(self, sample: IMUSample) -> None:
        if self._last_sequence is not None and sample.sequence > self._last_sequence + 1:
            self.dropped_samples += sample.sequence - self._last_sequence - 1
        if self._last_sequence is None or sample.sequence > self._last_sequence:
            self._last_sequence = sample.sequence
        self._points.append((sample.sequence, sample.received_timestamp_ns))

    @property
    def receive_rate_hz(self) -> float:
        if len(self._points) < 2:
            return 0.0
        first_sequence, first_time_ns = self._points[0]
        last_sequence, last_time_ns = self._points[-1]
        elapsed_s = (last_time_ns - first_time_ns) / 1_000_000_000.0
        if elapsed_s <= 0:
            return 0.0
        return max(0.0, (last_sequence - first_sequence) / elapsed_s)

    def reset(self) -> None:
        self._points.clear()
        self._last_sequence = None
        self.dropped_samples = 0
