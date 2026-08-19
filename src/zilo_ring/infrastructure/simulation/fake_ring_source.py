from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable

from zilo_ring.domain import IMUBatch, IMUSample, RingDevice, Vector3
from zilo_ring.ports import BatchHandler


class FakeRingSource:
    """Deterministic 100 Hz source for UI development without hardware."""

    async def connect(self, address: str) -> RingDevice:
        await asyncio.sleep(0.15)
        return RingDevice(
            address=address or "DE:MO:00:00:00:01",
            name="Zilo Demo Ring",
            battery_percent=88,
            nominal_sample_rate_hz=100.0,
        )

    async def stream(
        self,
        on_batch: BatchHandler,
        should_stop: Callable[[], bool],
    ) -> None:
        sequence = 0
        while not should_stop():
            samples = []
            received_ns = time.monotonic_ns()
            for _ in range(5):
                t = sequence / 100.0
                roll = math.radians(28.0 * math.sin(t * 1.4))
                pitch = math.radians(18.0 * math.sin(t * 0.9))
                accel = Vector3(
                    -math.sin(pitch),
                    math.sin(roll) * math.cos(pitch),
                    math.cos(roll) * math.cos(pitch),
                )
                gyro = Vector3(
                    39.2 * math.cos(t * 1.4),
                    16.2 * math.cos(t * 0.9),
                    12.0 * math.sin(t * 0.5),
                )
                samples.append(
                    IMUSample(
                        sequence=sequence,
                        device_timestamp_ms=int(t * 1000),
                        received_timestamp_ns=received_ns,
                        accel_raw=Vector3(*(value * 2048 for value in accel.as_tuple())),
                        gyro_raw=Vector3(*(value * 16 for value in gyro.as_tuple())),
                        accel_g=accel,
                        gyro_dps=gyro,
                    )
                )
                sequence += 1
            on_batch(
                IMUBatch(
                    samples=tuple(samples),
                    nominal_sample_rate_hz=100.0,
                    accel_range_g=16.0,
                    gyro_range_dps=2000.0,
                )
            )
            await asyncio.sleep(0.05)

    async def disconnect(self) -> None:
        return None
