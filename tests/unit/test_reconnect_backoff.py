from __future__ import annotations

import pytest

from zilo_ring.application.ring_controller import _reconnect_delay


def test_reconnect_delay_is_exponential_and_capped() -> None:
    values = [
        _reconnect_delay(
            base_delay_s=1.5,
            consecutive_failures=attempt,
            max_delay_s=12.0,
            jitter_ratio=0.0,
            jitter_sample=0.5,
        )
        for attempt in range(1, 6)
    ]
    assert values == [1.5, 3.0, 6.0, 12.0, 12.0]


def test_reconnect_jitter_stays_bounded() -> None:
    low = _reconnect_delay(
        base_delay_s=4.0,
        consecutive_failures=1,
        max_delay_s=12.0,
        jitter_ratio=0.2,
        jitter_sample=0.0,
    )
    high = _reconnect_delay(
        base_delay_s=4.0,
        consecutive_failures=1,
        max_delay_s=12.0,
        jitter_ratio=0.2,
        jitter_sample=1.0,
    )
    assert low == pytest.approx(3.2)
    assert high == pytest.approx(4.8)
