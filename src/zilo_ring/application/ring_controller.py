from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

from zilo_ring.domain import ConnectionState
from zilo_ring.ports import RingSource
from zilo_ring.state import AppStore


class RingController:
    """Owns one background BLE lifecycle without importing Qt or a concrete SDK."""

    def __init__(
        self,
        *,
        source_factory: Callable[[], RingSource],
        store: AppStore,
        reconnect_delay_s: float,
    ) -> None:
        self._source_factory = source_factory
        self._store = store
        self._reconnect_delay_s = reconnect_delay_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, address: str) -> None:
        address = address.strip()
        if not address:
            self._store.set_status(ConnectionState.ERROR, "Enter a ring MAC address")
            return
        if self.running:
            return
        self._stop_event.clear()
        self._store.reset_stream()
        self._thread = threading.Thread(
            target=lambda: asyncio.run(self._run(address)),
            name="zilo-ring-ble",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if not self.running:
            self._store.set_status(ConnectionState.IDLE, "Not connected")
            return
        self._store.set_status(ConnectionState.STOPPING, "Stopping ring")
        self._stop_event.set()

    def recenter(self) -> None:
        self._store.recenter()

    async def _run(self, address: str) -> None:
        reconnect_count = 0
        while not self._stop_event.is_set():
            source = self._source_factory()
            state = ConnectionState.CONNECTING if reconnect_count == 0 else ConnectionState.RECONNECTING
            self._store.set_status(
                state,
                "Connecting to ring" if reconnect_count == 0 else "Reconnecting to ring",
                address=address,
                reconnect_count=reconnect_count,
            )
            try:
                device = await source.connect(address)
                self._store.set_device(device)
                self._store.set_status(
                    ConnectionState.CONNECTING,
                    "Connected; waiting for IMU",
                    address=device.address,
                    reconnect_count=reconnect_count,
                )
                await source.stream(self._store.ingest, self._stop_event.is_set)
                if not self._stop_event.is_set():
                    raise RuntimeError("IMU stream stopped unexpectedly")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reconnect_count += 1
                self._store.set_status(
                    ConnectionState.RECONNECTING,
                    str(exc),
                    address=address,
                    reconnect_count=reconnect_count,
                )
                if not self._stop_event.is_set():
                    await asyncio.sleep(self._reconnect_delay_s)
            finally:
                try:
                    await source.disconnect()
                except Exception:
                    pass

        self._store.set_status(ConnectionState.IDLE, "Not connected", address=address)
