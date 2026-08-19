from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from zilo_ring.domain import IMUBatch, RingDevice


BatchHandler = Callable[[IMUBatch], None]


class RingSource(Protocol):
    async def connect(self, address: str) -> RingDevice:
        """Connect to one configured ring and return its metadata."""

    async def stream(
        self,
        on_batch: BatchHandler,
        should_stop: Callable[[], bool],
    ) -> None:
        """Read batches until stopped or the connection fails."""

    async def disconnect(self) -> None:
        """Stop sensor reporting and release the BLE connection."""
