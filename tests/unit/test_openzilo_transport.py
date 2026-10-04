from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

from bleak.backends.device import BLEDevice

from zilo_ring.infrastructure.bluetooth.bleak_nus_transport import BleakNusTransport
from zilo_ring.infrastructure.bluetooth.openzilo_ring_source import OpenZiloRingSource


class FakeClient:
    def __init__(self) -> None:
        self.is_connected = True
        self.notify_callback = None
        self.stopped_notifications: list[str] = []
        self.writes: list[tuple[str, bytes, bool]] = []
        self.disconnect_count = 0

    async def start_notify(self, uuid: str, callback) -> None:
        self.notify_callback = callback

    async def stop_notify(self, uuid: str) -> None:
        self.stopped_notifications.append(uuid)

    async def write_gatt_char(self, uuid: str, data: bytes, *, response: bool) -> None:
        self.writes.append((uuid, bytes(data), response))

    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self.is_connected = False


def test_transport_connects_with_ble_device_and_forwards_nus_data() -> None:
    async def scenario() -> None:
        device = BLEDevice("AA:BB:CC:DD:EE:FF", "Ring", {})
        client = FakeClient()
        connector_call: dict[str, Any] = {}

        async def connector(client_class, found_device, name, **kwargs):
            connector_call.update(
                client_class=client_class,
                device=found_device,
                name=name,
                kwargs=kwargs,
            )
            return client

        transport = BleakNusTransport(
            device=device,
            service_uuid="service",
            tx_uuid="tx",
            rx_uuid="rx",
            adapter="hci0",
            connector=connector,
        )
        received: list[bytes] = []
        disconnected: list[bool] = []
        transport.set_rx_callback(received.append)
        transport._set_disconnect_callback(lambda: disconnected.append(True))

        await transport.connect()
        assert connector_call["device"] is device
        assert connector_call["kwargs"]["bluez"] == {"adapter": "hci0"}
        assert connector_call["kwargs"]["max_attempts"] == 3

        assert client.notify_callback is not None
        client.notify_callback(None, bytearray(b"imu"))
        assert received == [b"imu"]

        await transport.write(bytes(range(45)))
        assert [len(write[1]) for write in client.writes] == [20, 20, 5]
        assert all(write[2] is False for write in client.writes)

        transport._handle_disconnect(client)
        assert disconnected == [True]
        await transport.disconnect()
        assert client.stopped_notifications == []
        assert client.disconnect_count == 1

    asyncio.run(scenario())


def test_openzilo_source_injects_the_scanned_device_without_a_second_scan(monkeypatch) -> None:
    async def scenario() -> None:
        device = BLEDevice("AA:BB:CC:DD:EE:FF", "Ring", {})
        captured: dict[str, Any] = {}
        scan_count = 0
        stale_cleanup: list[str] = []

        class FakeRingClient:
            is_connected = True

            def __init__(self, *, transport) -> None:
                captured["transport"] = transport

            async def connect(self) -> None:
                return None

        async def get_system_info(client, *, timeout_s: float):
            return SimpleNamespace(model="OpenZilo X", battery_percent=80)

        fake_sdk = SimpleNamespace(
            OpenZiloClient=FakeRingClient,
            get_system_info=get_system_info,
        )
        source = OpenZiloRingSource(
            scan_timeout_s=1.0,
            connect_timeout_s=1.0,
            sample_timeout_s=1.0,
            adapter="hci0",
            connect_attempts=3,
        )

        async def find_candidate(address: str):
            nonlocal scan_count
            scan_count += 1
            return device

        monkeypatch.setitem(sys.modules, "openzilo", fake_sdk)
        async def close_stale(address: str) -> None:
            stale_cleanup.append(address)

        monkeypatch.setattr(
            "zilo_ring.infrastructure.bluetooth.openzilo_ring_source.close_stale_connections_by_address",
            close_stale,
        )
        monkeypatch.setattr(source, "_find_candidate", find_candidate)

        ring = await source.connect(device.address)
        assert ring.address == device.address
        assert stale_cleanup == [device.address]
        assert scan_count == 1
        assert captured["transport"].device is device

    asyncio.run(scenario())


def test_openzilo_source_disconnect_tolerates_stop_packet_error(caplog) -> None:
    async def scenario() -> None:
        client = FakeClient()

        async def stop_sensor_report(_client, *, timeout_s: float) -> None:
            raise RuntimeError("Body CRC mismatch")

        source = OpenZiloRingSource(
            scan_timeout_s=1.0,
            connect_timeout_s=1.0,
            sample_timeout_s=1.0,
            adapter="hci0",
            connect_attempts=3,
        )
        source._sdk = SimpleNamespace(stop_sensor_report=stop_sensor_report)
        source._client = client

        await source.disconnect()

        assert client.disconnect_count == 1
        assert "Body CRC mismatch" in caplog.text

    asyncio.run(scenario())
