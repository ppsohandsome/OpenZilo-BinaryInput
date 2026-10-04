from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from bleak_retry_connector import close_stale_connections_by_address

from zilo_ring.domain import RingDevice
from zilo_ring.ports import BatchHandler

from .packet_mapper import map_sdk_batch
from .bleak_nus_transport import BleakNusTransport


NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
LOGGER = logging.getLogger(__name__)


class OpenZiloRingSource:
    """One-ring adapter using the public OpenZilo SDK API."""

    def __init__(
        self,
        *,
        scan_timeout_s: float,
        connect_timeout_s: float,
        sample_timeout_s: float,
        adapter: str,
        connect_attempts: int,
    ) -> None:
        self._scan_timeout_s = scan_timeout_s
        self._connect_timeout_s = connect_timeout_s
        self._sample_timeout_s = sample_timeout_s
        self._adapter = adapter
        self._connect_attempts = connect_attempts
        self._sdk: Any | None = None
        self._client: Any | None = None
        self._report_info: Any | None = None

    async def connect(self, address: str) -> RingDevice:
        if not address.strip():
            raise ValueError("Ring MAC address is required")
        try:
            import openzilo as sdk
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "OpenZilo SDK is not installed. Install the sibling OpenZilo checkout "
                "with: python -m pip install -e ../OpenZilo"
            ) from exc
        self._sdk = sdk
        try:
            await asyncio.wait_for(
                close_stale_connections_by_address(address),
                timeout=5.0,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to clear stale BLE connection for {address}"
            ) from exc
        candidate = await self._find_candidate(address)
        candidate_address = str(getattr(candidate, "address", None) or address)
        transport = BleakNusTransport(
            device=candidate,
            service_uuid=NUS_SERVICE_UUID,
            tx_uuid=NUS_TX_UUID,
            rx_uuid=NUS_RX_UUID,
            adapter=self._adapter,
            max_connect_attempts=self._connect_attempts,
        )
        client = self._sdk.OpenZiloClient(transport=transport)
        await asyncio.wait_for(client.connect(), timeout=self._connect_timeout_s)
        self._client = client
        try:
            await asyncio.sleep(0.25)
            info = await self._sdk.get_system_info(client, timeout_s=10.0)
            return RingDevice(
                address=candidate_address,
                name=str(getattr(info, "model", "OpenZilo Ring") or "OpenZilo Ring"),
                battery_percent=_optional_int(getattr(info, "battery_percent", None)),
            )
        except Exception:
            await self.disconnect()
            raise

    async def stream(
        self,
        on_batch: BatchHandler,
        should_stop: Callable[[], bool],
    ) -> None:
        if self._sdk is None or self._client is None:
            raise RuntimeError("Ring is not connected")

        report = await self._sdk.start_sensor_report(self._client, timeout_s=8.0)
        self._report_info = report
        sample_rate_hz = float(getattr(report, "sample_rate_hz", 0.0) or 0.0)
        accel_range_g = _optional_float(getattr(report, "accel_range_g", None))
        gyro_range_dps = _optional_float(getattr(report, "gyro_range_dps", None))
        consecutive_timeouts = 0
        consecutive_protocol_errors = 0

        while not should_stop():
            try:
                raw_batch = await self._sdk.wait_sensor_data(
                    self._client,
                    timeout_s=self._sample_timeout_s,
                )
            except Exception as exc:
                if isinstance(exc, getattr(self._sdk, "TimeoutError", TimeoutError)):
                    consecutive_timeouts += 1
                    if consecutive_timeouts < 3:
                        continue
                    raise RuntimeError("No IMU samples after three timeouts") from exc
                if isinstance(exc, getattr(self._sdk, "ProtocolError", ValueError)):
                    consecutive_protocol_errors += 1
                    if consecutive_protocol_errors < 10:
                        continue
                    raise RuntimeError("Repeated malformed IMU packets") from exc
                raise

            consecutive_timeouts = 0
            consecutive_protocol_errors = 0
            batch = map_sdk_batch(
                raw_batch,
                nominal_sample_rate_hz=sample_rate_hz,
                accel_range_g=accel_range_g,
                gyro_range_dps=gyro_range_dps,
            )
            if batch.samples:
                on_batch(batch)

    async def disconnect(self) -> None:
        sdk, client = self._sdk, self._client
        self._report_info = None
        self._client = None
        stop_error: Exception | None = None
        disconnect_error: Exception | None = None
        if sdk is not None and client is not None:
            try:
                if getattr(client, "is_connected", False):
                    await sdk.stop_sensor_report(client, timeout_s=5.0)
            except Exception as exc:
                stop_error = exc
            try:
                await client.disconnect()
            except Exception as exc:
                disconnect_error = exc
        if disconnect_error is not None:
            errors = [error for error in (stop_error, disconnect_error) if error]
            details = "; ".join(str(error) or type(error).__name__ for error in errors)
            raise RuntimeError(f"BLE cleanup failed: {details}") from disconnect_error
        if stop_error is not None:
            LOGGER.warning(
                "Sensor report stop failed; BLE link was disconnected: %s",
                str(stop_error) or type(stop_error).__name__,
            )

    async def _find_candidate(self, address: str) -> Any:
        try:
            from bleak import BleakScanner
        except ImportError as exc:
            raise RuntimeError("bleak is required for Linux BLE") from exc

        expected = _normalize_address(address)

        def matches(device: Any, advertisement: Any) -> bool:
            device_address = str(getattr(device, "address", ""))
            if expected and _normalize_address(device_address) != expected:
                return False
            advertised_uuids = {
                str(value).lower()
                for value in (getattr(advertisement, "service_uuids", None) or ())
            }
            return bool(expected) or NUS_SERVICE_UUID in advertised_uuids

        candidate = await BleakScanner.find_device_by_filter(
            matches,
            timeout=self._scan_timeout_s,
            bluez={"adapter": self._adapter},
        )
        if candidate is None:
            raise RuntimeError(f"Ring not found: {address}")
        return candidate


def _normalize_address(address: object) -> str:
    return "".join(ch for ch in str(address or "") if ch.isalnum()).lower()


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)
