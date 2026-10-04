from __future__ import annotations

from zilo_ring.bootstrap.single_instance import acquire_single_instance_lock


def test_single_instance_lock_blocks_then_releases(tmp_path) -> None:
    lock_path = tmp_path / "zilo-ring.lock"
    first = acquire_single_instance_lock(lock_path)
    assert first is not None
    try:
        assert acquire_single_instance_lock(lock_path) is None
    finally:
        first.close()

    replacement = acquire_single_instance_lock(lock_path)
    assert replacement is not None
    replacement.close()
