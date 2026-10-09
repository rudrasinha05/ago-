"""Explicit, versioned event contracts and payload validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ago.events import Event

Validator = Callable[[dict[str, Any]], None]


class EventContractError(ValueError):
    pass


@dataclass(frozen=True)
class EventContract:
    name: str
    version: int
    validator: Validator

    def __post_init__(self) -> None:
        if not self.name or self.version < 1 or not callable(self.validator):
            raise EventContractError("Invalid event contract")


class EventRegistry:
    def __init__(self) -> None:
        self._contracts: dict[tuple[str, int], EventContract] = {}

    def register(self, contract: EventContract) -> None:
        key = (contract.name, contract.version)
        if key in self._contracts:
            raise EventContractError(f"Duplicate contract: {key}")
        self._contracts[key] = contract

    def validate(self, event: Event) -> None:
        if not isinstance(event.payload, dict):
            raise EventContractError("Event payload must be an object")
        version = event.payload.get("_version", 1)
        if type(version) is not int or version < 1:
            raise EventContractError("Invalid event version")
        contract = self._contracts.get((event.name, version))
        if contract is None:
            raise EventContractError(f"Unknown contract: {event.name} v{version}")
        try:
            contract.validator(event.payload)
        except EventContractError:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise EventContractError(str(exc)) from exc


def require_fields(*fields: str) -> Validator:
    """Small deterministic schema guard; use richer validators per domain."""
    def validate(payload: dict[str, Any]) -> None:
        missing = [name for name in fields if name not in payload]
        if missing:
            raise EventContractError(f"Missing fields: {', '.join(missing)}")
    return validate
