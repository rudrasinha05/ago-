"""M1.8 in-process monotonic interval scheduler; not a durable job queue."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: float
    handler: Callable[[], Awaitable[None]]
    next_run: float


class IntervalScheduler:
    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}

    def add(self, name: str, interval_seconds: float, handler: Callable[[], Awaitable[None]]) -> None:
        if not name or interval_seconds <= 0 or name in self._jobs:
            raise ValueError("Invalid or duplicate job")
        self._jobs[name] = ScheduledJob(
            name, interval_seconds, handler, time.monotonic() + interval_seconds
        )

    async def tick(self, *, now: float | None = None) -> list[str]:
        timestamp = time.monotonic() if now is None else now
        executed = []
        for job in self._jobs.values():
            if job.next_run <= timestamp:
                job.next_run = timestamp + job.interval_seconds
                await job.handler()
                executed.append(job.name)
        return executed

    async def serve(self, stop: asyncio.Event, *, poll_seconds: float = 0.5) -> None:
        if poll_seconds <= 0:
            raise ValueError("Poll interval must be positive")
        while not stop.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass
