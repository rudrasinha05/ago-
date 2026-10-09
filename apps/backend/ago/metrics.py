"""M1.9 lightweight thread-safe counters and timing summaries."""
from __future__ import annotations

import threading
from collections import defaultdict


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._durations: dict[str, tuple[int, float]] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        if not name or amount < 0:
            raise ValueError("Invalid counter")
        with self._lock:
            self._counters[name] += amount

    def observe(self, name: str, seconds: float) -> None:
        if not name or not 0 <= seconds < float("inf"):
            raise ValueError("Invalid observation")
        with self._lock:
            count, total = self._durations.get(name, (0, 0.0))
            self._durations[name] = (count + 1, total + seconds)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "durations": {
                    name: {"count": count, "total_seconds": total}
                    for name, (count, total) in self._durations.items()
                },
            }
