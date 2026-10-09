import sqlite3

import pytest

from ago.event_store import SqliteEventStore
from ago.events import Event


def test_outbox_persists_and_delivers(tmp_path):
    path = tmp_path / "events.sqlite"
    store = SqliteEventStore(path)
    event = Event("task.created", {"task_id": 123}, correlation_id="trace-1")
    store.enqueue(event)
    assert store.pending() == [event]
    store.delivered(event.id)
    assert store.pending() == []
    store.close()
    reopened = SqliteEventStore(path)
    assert reopened.pending() == []
    reopened.close()


def test_outbox_transaction_rolls_back():
    store = SqliteEventStore()
    event = Event("test", {})
    with pytest.raises(RuntimeError):
        with store.transaction() as db:
            store.enqueue(event, db)
            raise RuntimeError("rollback")
    assert store.pending() == []
    store.close()


def test_inbox_exactly_once_local_transaction():
    store = SqliteEventStore()
    event = Event("job", {})
    calls = []

    def handler(db, received):
        calls.append(received.id)

    assert store.handle_once("worker-a", event, handler)
    assert not store.handle_once("worker-a", event, handler)
    assert store.handle_once("worker-b", event, handler)
    assert calls == [event.id, event.id]
    store.close()


def test_inbox_rolls_back_handler_failure():
    store = SqliteEventStore()
    event = Event("job", {})

    def handler(db, received):
        db.execute("CREATE TABLE IF NOT EXISTS side_effects (id TEXT)")
        db.execute("INSERT INTO side_effects VALUES (?)", (received.id,))
        raise RuntimeError("failed")

    with pytest.raises(RuntimeError, match="failed"):
        store.handle_once("worker", event, handler)
    assert not store.already_handled("worker", event.id)
    store.close()


def test_failed_event_retries_and_dead_letters():
    store = SqliteEventStore()
    event = Event("job", {})
    store.enqueue(event)
    store.failed(event.id, "temporary", max_attempts=2)
    assert store.connection.execute(
        "SELECT status FROM event_outbox WHERE id=?", (event.id,)
    ).fetchone()["status"] == "pending"
    store.failed(event.id, "permanent", max_attempts=2)
    row = store.connection.execute(
        "SELECT status, attempts FROM event_outbox WHERE id=?", (event.id,)
    ).fetchone()
    assert row["status"] == "dead" and row["attempts"] == 2
    store.close()


def test_invalid_limit_and_duplicate_event():
    store = SqliteEventStore()
    with pytest.raises(ValueError):
        store.pending(0)
    event = Event("job", {})
    store.enqueue(event)
    with pytest.raises(sqlite3.IntegrityError):
        store.enqueue(event)
    store.close()
