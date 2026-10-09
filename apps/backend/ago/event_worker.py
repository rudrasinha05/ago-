"""Operational PostgreSQL outbox dispatcher.

At-least-once delivery: handlers must be idempotent. Each worker owns its store.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from ago.events import Event

logger = logging.getLogger("ago.event_worker")


class LeasedStore(Protocol):
    def claim(self, worker_id: str, limit: int = 100, lease_seconds: int = 60) -> list[Event]: ...
    def delivered(self, event_id: str, worker_id: str) -> bool: ...
    def failed(self, event_id: str, worker_id: str, error: str, max_attempts: int = 3) -> bool: ...


@dataclass(frozen=True)
class WorkerReport:
    claimed: int
    delivered: int
    failed: int
    lost_leases: int


class EventWorker:
    def __init__(
        self,
        store: LeasedStore,
        worker_id: str,
        handler: Callable[[Event], Awaitable[None]],
        *,
        batch_size: int = 50,
        lease_seconds: int = 60,
        max_attempts: int = 3,
    ):
        if not worker_id or not 1 <= batch_size <= 1000 or lease_seconds < 1 or max_attempts < 1:
            raise ValueError("Invalid worker configuration")
        self.store = store
        self.worker_id = worker_id
        self.handler = handler
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    async def run_once(self) -> WorkerReport:
        """Claim and dispatch one batch. Uses thread offloading for synchronous DB calls."""
        events = await asyncio.to_thread(
            self.store.claim, self.worker_id, self.batch_size, self.lease_seconds
        )
        delivered = failed = lost = 0
        for event in events:
            try:
                await self.handler(event)
            except asyncio.CancelledError:
                # Lease expires and another worker can recover the event.
                raise
            except Exception as exc:
                acknowledged = await asyncio.to_thread(
                    self.store.failed, event.id, self.worker_id,
                    f"{type(exc).__name__}: {exc}", self.max_attempts,
                )
                if acknowledged:
                    failed += 1
                else:
                    lost += 1
                logger.exception("Outbox handler failed: event_id=%s", event.id)
            else:
                if await asyncio.to_thread(self.store.delivered, event.id, self.worker_id):
                    delivered += 1
                else:
                    lost += 1
        return WorkerReport(len(events), delivered, failed, lost)

    async def run_forever(self, stop: asyncio.Event, poll_seconds: float = 1.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while not stop.is_set():
            report = await self.run_once()
            if report.claimed:
                continue
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass
