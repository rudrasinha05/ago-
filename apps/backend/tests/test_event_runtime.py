from pathlib import Path

import pytest

from ago.event_runtime import migration_directory, serve_worker
from ago.events import EventBus


def test_migration_directory_points_to_repository():
    directory = migration_directory()
    assert isinstance(directory, Path)
    assert (directory / "001_events_postgres.sql").exists()


def test_worker_does_not_start_without_postgres(monkeypatch):
    class BrokenStore:
        def __init__(self, dsn):
            raise RuntimeError("connection unavailable")

    monkeypatch.setattr("ago.event_runtime.PostgresEventStore", BrokenStore)
    import asyncio

    with pytest.raises(RuntimeError, match="connection unavailable"):
        asyncio.run(serve_worker("bad-dsn", EventBus(), worker_id="worker"))


def test_worker_retries_unhandled_events(monkeypatch):
    import asyncio
    from ago.events import Event

    stop = __import__("asyncio").Event()

    class Store:
        instance = None

        def __init__(self, dsn):
            self.event = Event("unhandled", {"id": 1})
            self.failures = []
            Store.instance = self

        def claim(self, worker_id, limit=100, lease_seconds=60):
            return [self.event]

        def failed(self, event_id, worker_id, error, max_attempts=3):
            self.failures.append(error)
            stop.set()
            return True

        def delivered(self, event_id, worker_id):
            raise AssertionError("Unhandled event must not be delivered")

        def close(self):
            pass

    monkeypatch.setattr("ago.event_runtime.PostgresEventStore", Store)

    async def run():
        await serve_worker("unused", EventBus(), worker_id="worker", stop=stop)

    asyncio.run(run())
    assert Store.instance.failures
    assert "No handler registered" in Store.instance.failures[0]
