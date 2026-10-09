import asyncio

import pytest

from ago.events import Event, EventBus


def test_dispatch_and_unsubscribe():
    bus = EventBus()
    seen = []
    unsubscribe = bus.subscribe("task.created", lambda event: seen.append(event.payload["id"]))
    result = asyncio.run(bus.publish(Event("task.created", {"id": 7})))
    assert result.successful and result.delivered == 1
    assert seen == [7]
    unsubscribe()
    assert asyncio.run(bus.publish(Event("task.created", {}))).delivered == 0


def test_async_handler_and_wildcard():
    bus = EventBus()
    seen = []

    async def handler(event):
        await asyncio.sleep(0)
        seen.append(event.name)

    bus.subscribe("*", handler)
    result = asyncio.run(bus.publish(Event("task.completed", {})))
    assert result.successful and seen == ["task.completed"]


def test_retry_then_success():
    bus = EventBus(max_retries=2)
    attempts = []

    def flaky(event):
        attempts.append(event.id)
        if len(attempts) < 3:
            raise RuntimeError("temporary")

    bus.subscribe("job", flaky)
    result = asyncio.run(bus.publish(Event("job", {})))
    assert result.delivered == 1 and result.successful
    assert len(attempts) == 3


def test_handler_failure_isolated():
    bus = EventBus(max_retries=1)
    called = []

    def failing(event):
        raise ValueError("bad")

    bus.subscribe("job", failing)
    bus.subscribe("job", lambda event: called.append(event.id))
    result = asyncio.run(bus.publish(Event("job", {})))
    assert not result.successful
    assert result.delivered == 1
    assert result.failures[0].attempts == 2
    assert len(called) == 1


def test_duplicate_subscription_rejected():
    bus = EventBus()
    handler = lambda event: None
    bus.subscribe("job", handler)
    with pytest.raises(ValueError, match="already subscribed"):
        bus.subscribe("job", handler)


def test_cancelled_handler_propagates():
    bus = EventBus()

    async def cancel(event):
        raise asyncio.CancelledError()

    bus.subscribe("job", cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(bus.publish(Event("job", {})))


def test_invalid_configuration():
    with pytest.raises(ValueError):
        EventBus(max_retries=-1)
    with pytest.raises(ValueError):
        EventBus(max_retries=11)
    with pytest.raises(ValueError):
        asyncio.run(EventBus().publish(Event("", {})))


def test_event_bus_registered_in_application_container():
    from ago.platform import build_container

    container = build_container()
    assert container.resolve("event_bus") is container.resolve("event_bus")
    assert isinstance(container.resolve("event_bus"), EventBus)
