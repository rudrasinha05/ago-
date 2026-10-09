"""In-process event bus with bounded retries, typed envelopes and handler isolation.

Not a durable broker: cross-process delivery requires a transactional outbox.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger("ago.events")


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None


Handler = Callable[[Event], Awaitable[None] | None]


@dataclass(frozen=True)
class DeliveryFailure:
    event_id: str
    handler_name: str
    attempts: int
    error: str


@dataclass
class DispatchResult:
    event_id: str
    delivered: int = 0
    failures: list[DeliveryFailure] = field(default_factory=list)

    @property
    def successful(self) -> bool:
        return not self.failures


class EventBus:
    """Async, ordered, per-event handler dispatch; failures do not stop later handlers."""

    def __init__(self, max_retries: int = 0):
        if max_retries < 0 or max_retries > 10:
            raise ValueError("max_retries must be between 0 and 10")
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._max_retries = max_retries

    def subscribe(self, event_name: str, handler: Handler) -> Callable[[], None]:
        if not event_name or not callable(handler):
            raise ValueError("event_name and callable handler are required")
        if handler in self._handlers[event_name]:
            raise ValueError(f"Handler already subscribed to {event_name}")
        self._handlers[event_name].append(handler)

        def unsubscribe() -> None:
            handlers = self._handlers.get(event_name, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def has_subscribers(self, event_name: str) -> bool:
        return bool(self._handlers.get(event_name) or self._handlers.get("*"))

    async def publish(self, event: Event) -> DispatchResult:
        if not event.name:
            raise ValueError("Event name must not be empty")
        result = DispatchResult(event_id=event.id)
        handlers = tuple(self._handlers.get(event.name, ())) + tuple(
            self._handlers.get("*", ())
        )
        for handler in handlers:
            attempts = 0
            while True:
                attempts += 1
                try:
                    value = handler(event)
                    if inspect.isawaitable(value):
                        await value
                    result.delivered += 1
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if attempts <= self._max_retries:
                        continue
                    failure = DeliveryFailure(
                        event_id=event.id,
                        handler_name=getattr(handler, "__name__", type(handler).__name__),
                        attempts=attempts,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    result.failures.append(failure)
                    logger.exception("Event handler failed: %s", failure.handler_name)
                    break
        return result
