from __future__ import annotations

from zilo_ring.bootstrap import create_ring_source
from zilo_ring.config import Settings
from zilo_ring.infrastructure.bluetooth import OpenZiloRingSource
from zilo_ring.infrastructure.simulation import FakeRingSource


def test_empty_mac_selects_virtual_source() -> None:
    source = create_ring_source("", settings=Settings())
    assert isinstance(source, FakeRingSource)


def test_non_empty_mac_selects_ble_source() -> None:
    source = create_ring_source("AA:BB:CC:DD:EE:FF", settings=Settings())
    assert isinstance(source, OpenZiloRingSource)
