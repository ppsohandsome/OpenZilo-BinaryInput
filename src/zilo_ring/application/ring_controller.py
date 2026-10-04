from __future__ import annotations

import asyncio
import logging
import random
import threading
from collections.abc import Callable

from zilo_ring.domain import ConnectionState
from zilo_ring.ports import RingSource
from zilo_ring.state import AppStore


LOGGER = logging.getLogger(__name__)


class RingController:
    """Owns one background BLE lifecycle without importing Qt or a concrete SDK."""

    def __init__(
        self,
        *,
        source_factory: Callable[[str], RingSource],
        store: AppStore,
        reconnect_delay_s: float,
        reconnect_max_delay_s: float,
        reconnect_jitter_ratio: float,
    ) -> None:
        self._source_factory = source_factory
        self._store = store
        self._reconnect_delay_s = reconnect_delay_s
        self._reconnect_max_delay_s = reconnect_max_delay_s
        self._reconnect_jitter_ratio = reconnect_jitter_ratio
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, address: str) -> bool:
        address = address.strip()
        if self.running:
            return False
        self._stop_event.clear()
        self._store.reset_stream()
        self._thread = threading.Thread(
            target=lambda: asyncio.run(self._run(address)),
            name="zilo-ring-ble",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, *, wait: bool = False, timeout_s: float | None = None) -> bool:
        thread = self._thread
        if thread is None or not thread.is_alive():
            self._store.set_status(ConnectionState.IDLE, "Not connected")
            return True
        self._store.set_status(ConnectionState.STOPPING, "Stopping ring")
        self._stop_event.set()
        if wait and thread is not threading.current_thread():
            thread.join(timeout=timeout_s)
        return not thread.is_alive()

    def recenter(self) -> None:
        self._store.recenter()

    async def _run(self, address: str) -> None:
        reconnect_count = 0
        consecutive_failures = 0
        cleanup_warning: str | None = None
        while not self._stop_event.is_set():
            source = self._source_factory(address)
            virtual = not address
            state = ConnectionState.CONNECTING if reconnect_count == 0 else ConnectionState.RECONNECTING
            self._store.set_status(
                state,
                (
                    "Starting virtual ring"
                    if virtual and reconnect_count == 0
                    else "Restarting virtual ring"
                    if virtual
                    else "Connecting to ring"
                    if reconnect_count == 0
                    else "Reconnecting to ring"
                ),
                address=address,
                reconnect_count=reconnect_count,
            )
            try:
                device = await source.connect(address)
                self._store.set_device(device)
                self._store.set_status(
                    ConnectionState.CONNECTING,
                    (
                        "Virtual ring ready; waiting for IMU"
                        if virtual
                        else "Connected; waiting for IMU"
                    ),
                    address=device.address,
                    reconnect_count=reconnect_count,
                )
                def ingest_and_reset_backoff(batch) -> None:
                    nonlocal consecutive_failures
                    consecutive_failures = 0
                    self._store.ingest(batch)

                await source.stream(ingest_and_reset_backoff, self._stop_event.is_set)
                if not self._stop_event.is_set():
                    raise RuntimeError("IMU stream stopped unexpectedly")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reconnect_count += 1
                consecutive_failures += 1
                delay = _reconnect_delay(
                    base_delay_s=self._reconnect_delay_s,
                    consecutive_failures=consecutive_failures,
                    max_delay_s=self._reconnect_max_delay_s,
                    jitter_ratio=self._reconnect_jitter_ratio,
                    jitter_sample=random.random(),
                )
                self._store.set_status(
                    ConnectionState.RECONNECTING,
                    f"{exc}; retrying in {delay:.1f}s",
                    address=address,
                    reconnect_count=reconnect_count,
                )
                if not self._stop_event.is_set():
                    await asyncio.to_thread(self._stop_event.wait, delay)
            finally:
                try:
                    await source.disconnect()
                except Exception as exc:
                    LOGGER.warning("Ring cleanup failed: %s", exc, exc_info=True)
                    if self._stop_event.is_set():
                        cleanup_warning = str(exc)

        if cleanup_warning:
            self._store.set_status(
                ConnectionState.ERROR,
                f"Disconnected with cleanup error: {cleanup_warning}",
                address=address,
            )
        else:
            self._store.set_status(ConnectionState.IDLE, "Not connected", address=address)


def _reconnect_delay(
    *,
    base_delay_s: float,
    consecutive_failures: int,
    max_delay_s: float,
    jitter_ratio: float,
    jitter_sample: float,
) -> float:
    exponent = max(0, consecutive_failures - 1)
    uncapped = base_delay_s * (2**exponent)
    capped = min(max_delay_s, uncapped)
    jitter = capped * max(0.0, jitter_ratio) * (2.0 * jitter_sample - 1.0)
    return min(max_delay_s, max(0.0, capped + jitter))
