from __future__ import annotations

import time

from zilo_ring.domain import IMUBatch, IMUSample, Vector3
from zilo_ring.processing import ComplementaryOrientationEstimator, ProcessingPipeline
from zilo_ring.state import AppStore


def test_store_keeps_bounded_history_and_latest_sample() -> None:
    store = AppStore(
        processor=ProcessingPipeline(ComplementaryOrientationEstimator()),
        history_size=2,
        stale_after_ms=500,
    )
    samples = tuple(
        IMUSample(
            sequence=index,
            device_timestamp_ms=index * 10,
            received_timestamp_ns=time.monotonic_ns(),
            accel_raw=Vector3(0, 0, 2048),
            gyro_raw=Vector3(0, 0, 0),
            accel_g=Vector3(0, 0, 1),
            gyro_dps=Vector3(0, 0, 0),
        )
        for index in range(3)
    )
    store.ingest(IMUBatch(samples, 100.0, 16.0, 2000.0))
    snapshot = store.snapshot()
    assert [sample.sequence for sample in snapshot.history] == [1, 2]
    assert snapshot.ring.latest_sample is samples[-1]
