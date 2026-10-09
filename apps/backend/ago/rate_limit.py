"""Thread-safe, bounded in-process fixed-window limiter.

For development and single-process deployments only; distributed enforcement
requires Redis or another shared atomic store.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, *, limit: int = 5, window_seconds: int = 60, max_keys: int = 10000):
        if limit < 1 or window_seconds < 1 or max_keys < 1:
            raise ValueError("Invalid limiter configuration")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        if not key:
            raise ValueError("Limiter key required")
        timestamp = time.monotonic() if now is None else now
        bucket = int(timestamp // self.window_seconds)
        with self._lock:
            count, current = self._hits.get(key, (0, bucket))
            if current != bucket:
                count = 0
            if count >= self.limit:
                return False
            if key not in self._hits and len(self._hits) >= self.max_keys:
                self._hits = {
                    k: v for k, v in self._hits.items() if v[1] == bucket
                }
                if len(self._hits) >= self.max_keys:
                    return False
            self._hits[key] = (count + 1, bucket)
            return True
