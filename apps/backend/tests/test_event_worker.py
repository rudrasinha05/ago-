import asyncio

import pytest

from ago.events import Event
from ago.event_worker import EventWorker


class FakeStore:
    def __init__(self, events):
        self.events = events
        self.acks = []
        self.errors = []

    def claim(self, worker_id, limit=100, lease_seconds=60):
        events, self.events = self.events[:limit], self.events[limit:]
        return events

    def delivered(self, event_id, worker_id):
        self.acks.append((event_id, worker_id))
        return True

    def failed(self, event_id, worker_id, error, max_attempts=3):
        self.errors.append((event_id, worker_id, error))
        return True


def test_worker_successful_batch():
    event = Event("task.created", {"id": 1})
    store = FakeStore([event])
    seen = []

    async def handler(item):
        seen.append(item.id)

    report = asyncio.run(EventWorker(store, "worker-a", handler).run_once())
    assert (report.claimed, report.delivered, report.failed) == (1, 1, 0)
    assert seen == [event.id]
    assert store.acks == [(event.id, "worker-a")]


def test_worker_isolates_handler_failure():
    events = [Event("fail", {}), Event("ok", {})]
    store = FakeStore(events)

    async def handler(item):
        if item.name == "fail":
            raise RuntimeError("transient")

    report = asyncio.run(EventWorker(store, "worker-a", handler).run_once())
    assert (report.claimed, report.delivered, report.failed) == (2, 1, 1)
    assert len(store.errors) == 1


def test_worker_rejects_invalid_configuration():
    store = FakeStore([])

    async def handler(item):
        pass

    with pytest.raises(ValueError):
        EventWorker(store, "", handler)
    with pytest.raises(ValueError):
        EventWorker(store, "worker", handler, batch_size=0)


def test_worker_stops_gracefully():
    store = FakeStore([])

    async def handler(item):
        pass

    async def run():
        stop = asyncio.Event()
        stop.set()
        await EventWorker(store, "worker", handler).run_forever(stop, poll_seconds=0.01)

    asyncio.run(run())
