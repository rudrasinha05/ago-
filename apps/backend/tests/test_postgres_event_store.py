"""PostgreSQL integration tests require AGO_TEST_POSTGRES_DSN and a migrated test DB."""
import os

import pytest

from ago.events import Event
from ago.postgres_event_store import PostgresEventStore


@pytest.fixture
def store():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set AGO_TEST_POSTGRES_DSN for PostgreSQL integration tests")
    instance = PostgresEventStore(dsn)
    yield instance
    instance.close()


def test_postgres_outbox_claim_ack(store):
    event = Event("integration.created", {"count": 1})
    store.enqueue(event)
    claimed = store.claim("test-worker", limit=100)
    assert event.id in [item.id for item in claimed]
    assert store.delivered(event.id, "test-worker")
    assert not store.delivered(event.id, "other-worker")


def test_postgres_failed_lease_owner(store):
    event = Event("integration.failed", {})
    store.enqueue(event)
    assert event.id in [item.id for item in store.claim("failure-worker")]
    assert not store.failed(event.id, "wrong-worker", "error")
    assert store.failed(event.id, "failure-worker", "error", max_attempts=1)


def test_postgres_inbox_deduplicates(store):
    event = Event("integration.inbox", {})
    called = []

    def handler(connection, incoming):
        called.append(incoming.id)

    assert store.handle_once("test-consumer", event, handler)
    assert not store.handle_once("test-consumer", event, handler)
    assert called == [event.id]


def test_postgres_enqueue_rollback(store):
    event = Event("integration.rollback", {})
    with pytest.raises(RuntimeError):
        with store.transaction() as connection:
            store.enqueue(event, connection)
            raise RuntimeError("rollback")
    assert event.id not in [item.id for item in store.pending(1000)]


def test_postgres_dead_letter_replay(store):
    event = Event("integration.replay", {})
    store.enqueue(event)
    assert event.id in [item.id for item in store.claim("replay-worker")]
    assert store.renew_lease(event.id, "replay-worker", 30)
    assert not store.renew_lease(event.id, "wrong-worker", 30)
    assert store.failed(event.id, "replay-worker", "failed", max_attempts=1)
    assert event.id in [item.id for item in store.dead_letters()]
    assert store.replay_dead_letter(event.id)
    assert not store.replay_dead_letter(event.id)
    assert event.id in [item.id for item in store.pending()]
