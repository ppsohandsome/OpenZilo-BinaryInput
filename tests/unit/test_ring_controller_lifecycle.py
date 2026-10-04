from __future__ import annotations

import asyncio
import threading
from typing import Any

from zilo_ring.application import RingController
from zilo_ring.domain import ConnectionState, RingDevice


class RecordingStore:
    def __init__(self) -> None:
        self.statuses: list[tuple[ConnectionState, str]] = []

    def reset_stream(self) -> None:
        return None

    def set_device(self, _device: RingDevice) -> None:
        return None

    def ingest(self, _batch: Any) -> None:
        return None

    def set_status(self, state: ConnectionState, message: str, **_kwargs: Any) -> None:
        self.statuses.append((state, message))

    def recenter(self) -> None:
        return None


class BlockingSource:
    def __init__(self, *, cleanup_error: Exception | None = None) -> None:
        self.connected = threading.Event()
        self.disconnected = threading.Event()
        self.cleanup_error = cleanup_error

    async def connect(self, address: str) -> RingDevice:
        self.connected.set()
        return RingDevice(address=address)

    async def stream(self, _on_batch, should_stop) -> None:
        while not should_stop():
            await asyncio.sleep(0.005)

    async def disconnect(self) -> None:
        self.disconnected.set()
        if self.cleanup_error is not None:
            raise self.cleanup_error


def make_controller(source: BlockingSource, store: RecordingStore) -> RingController:
    return RingController(
        source_factory=lambda _address: source,
        store=store,  # type: ignore[arg-type]
        reconnect_delay_s=0.01,
        reconnect_max_delay_s=0.01,
        reconnect_jitter_ratio=0.0,
    )


def test_stop_can_wait_until_disconnect_finishes() -> None:
    source = BlockingSource()
    store = RecordingStore()
    controller = make_controller(source, store)

    assert controller.start("AA:BB:CC:DD:EE:FF") is True
    assert source.connected.wait(timeout=1.0)
    assert controller.start("AA:BB:CC:DD:EE:FF") is False

    assert controller.stop(wait=True, timeout_s=1.0) is True
    assert source.disconnected.is_set()
    assert controller.running is False
    assert store.statuses[-1] == (ConnectionState.IDLE, "Not connected")


def test_cleanup_failure_is_visible_after_stop() -> None:
    source = BlockingSource(cleanup_error=RuntimeError("disconnect failed"))
    store = RecordingStore()
    controller = make_controller(source, store)

    assert controller.start("AA:BB:CC:DD:EE:FF") is True
    assert source.connected.wait(timeout=1.0)
    assert controller.stop(wait=True, timeout_s=1.0) is True

    state, message = store.statuses[-1]
    assert state == ConnectionState.ERROR
    assert "disconnect failed" in message
