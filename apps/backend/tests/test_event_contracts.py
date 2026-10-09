import pytest

from ago.event_contracts import (
    EventContract, EventContractError, EventRegistry, require_fields,
)
from ago.events import Event


def test_versioned_event_contract():
    registry = EventRegistry()
    registry.register(EventContract("task.created", 1, require_fields("task_id")))
    registry.register(EventContract("task.created", 2, require_fields("task_id", "owner")))
    registry.validate(Event("task.created", {"task_id": "123"}))
    registry.validate(Event("task.created", {"_version": 2, "task_id": "123", "owner": "a"}))
    with pytest.raises(EventContractError, match="Missing fields"):
        registry.validate(Event("task.created", {"_version": 2, "task_id": "123"}))


def test_unknown_invalid_and_duplicate_contracts():
    registry = EventRegistry()
    contract = EventContract("task.created", 1, require_fields("task_id"))
    registry.register(contract)
    with pytest.raises(EventContractError, match="Duplicate"):
        registry.register(contract)
    with pytest.raises(EventContractError, match="Unknown"):
        registry.validate(Event("other", {}))
    with pytest.raises(EventContractError, match="Invalid event version"):
        registry.validate(Event("task.created", {"_version": True}))
    with pytest.raises(EventContractError, match="Invalid event contract"):
        EventContract("", 1, require_fields("x"))
