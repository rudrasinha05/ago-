"""Operational entrypoints for AGO PostgreSQL event migrations and outbox worker."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
from pathlib import Path

from ago.event_migrations import apply_migrations
from ago.event_worker import EventWorker
from ago.events import EventBus
from ago.postgres_event_store import PostgresEventStore

logger = logging.getLogger(__name__)


def migration_directory() -> Path:
    return Path(__file__).resolve().parents[3] / "deploy" / "sql"


def migrate(dsn: str, directory: Path | None = None) -> list[str]:
    store = PostgresEventStore(dsn)
    try:
        return apply_migrations(store.connection, directory or migration_directory())
    finally:
        store.close()


async def serve_worker(
    dsn: str, bus: EventBus, *, worker_id: str, poll_seconds: float = 1.0,
    stop: asyncio.Event | None = None,
) -> None:
    """Dispatch registered bus handlers; failures are retried via the outbox."""
    store = PostgresEventStore(dsn)
    stop = stop or asyncio.Event()

    async def dispatch(event):
        result = await bus.publish(event)
        if result.failures:
            raise RuntimeError(
                f"{len(result.failures)} event handler(s) failed for {event.id}"
            )

    worker = EventWorker(store, worker_id, dispatch)
    try:
        await worker.run_forever(stop, poll_seconds)
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="AGO event infrastructure operations")
    parser.add_argument("command", choices=("migrate", "worker"))
    parser.add_argument("--dsn", default=os.getenv("AGO_POSTGRES_DSN"))
    parser.add_argument("--worker-id", default=os.getenv("AGO_WORKER_ID", "ago-worker-1"))
    args = parser.parse_args()
    if not args.dsn:
        parser.error("PostgreSQL DSN required (--dsn or AGO_POSTGRES_DSN)")
    if args.command == "migrate":
        for name in migrate(args.dsn):
            print(f"Applied: {name}")
        return

    # Deliberately refuse to start without a configured domain handler registry.
    # Empty buses would silently mark events delivered without processing them.
    parser.error(
        "Worker requires application-registered event handlers. "
        "Use serve_worker(dsn, configured_bus, worker_id=...) from application startup."
    )


if __name__ == "__main__":
    main()
