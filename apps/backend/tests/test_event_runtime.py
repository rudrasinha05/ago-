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
