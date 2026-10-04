from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection


RxCallback = Callable[[bytes], None | Awaitable[None]]
DisconnectCallback = Callable[[], None | Awaitable[None]]
Connector = Callable[..., Awaitable[Any]]


class BleakNusTransport:
    """Reliable one-device Nordic UART Service transport for OpenZiloClient."""

    def __init__(
        self,
        *,
        device: BLEDevice,
        service_uuid: str,
        tx_uuid: str,
        rx_uuid: str,
        adapter: str,
        max_connect_attempts: int = 3,
        write_chunk_size: int = 20,
        connector: Connector = establish_connection,
        client_class: type[Any] = BleakClientWithServiceCache,
    ) -> None:
        self.device = device
        self.service_uuid = service_uuid
        self.tx_uuid = tx_uuid
        self.rx_uuid = rx_uuid
        self.adapter = adapter
        self.max_connect_attempts = max_connect_attempts
        self.write_chunk_size = write_chunk_size
        self._connector = connector
        self._client_class = client_class
        self._client: Any | None = None
        self._rx_callback: RxCallback | None = None
        self._disconnect_callback: DisconnectCallback | None = None
        self._notify_started = False

    def set_rx_callback(self, callback: RxCallback | None) -> None:
        self._rx_callback = callback

    def _set_disconnect_callback(self, callback: DisconnectCallback | None) -> None:
        self._disconnect_callback = callback

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    async def connect(self) -> None:
        if self.is_connected:
            return
        client = await self._connector(
            self._client_class,
            self.device,
            self.device.name or self.device.address,
            disconnected_callback=self._handle_disconnect,
            max_attempts=self.max_connect_attempts,
            use_services_cache=True,
            services={self.service_uuid},
            bluez={"adapter": self.adapter},
        )
        self._client = client
        try:
            await client.start_notify(self.tx_uuid, self._handle_notify)
            self._notify_started = True
        except Exception:
            self._client = None
            await client.disconnect()
            raise

    async def disconnect(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            if self._notify_started and client.is_connected:
                await client.stop_notify(self.tx_uuid)
        finally:
            self._notify_started = False
            if client.is_connected:
                await client.disconnect()

    async def write(self, data: bytes | bytearray | memoryview) -> None:
        client = self._client
        if client is None or not client.is_connected:
            raise RuntimeError("BLE client is not connected")
        payload = bytes(data)
        for offset in range(0, len(payload), self.write_chunk_size):
            await client.write_gatt_char(
                self.rx_uuid,
                payload[offset : offset + self.write_chunk_size],
                response=False,
            )
            await asyncio.sleep(0)

    def _handle_notify(self, _sender: Any, data: bytearray) -> None:
        callback = self._rx_callback
        if callback is None:
            return
        result = callback(bytes(data))
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)

    def _handle_disconnect(self, _client: Any) -> None:
        self._notify_started = False
        callback = self._disconnect_callback
        if callback is None:
            return
        result = callback()
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)
