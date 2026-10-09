from concurrent.futures import ThreadPoolExecutor

import pytest

from ago.metrics import Metrics


def test_metrics_thread_safe_and_snapshots():
    metrics = Metrics()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: metrics.increment("requests"), range(100)))
    metrics.observe("latency", 0.25)
    assert metrics.snapshot()["counters"]["requests"] == 100
    assert metrics.snapshot()["durations"]["latency"]["total_seconds"] == 0.25
    with pytest.raises(ValueError):
        metrics.observe("latency", -1)
