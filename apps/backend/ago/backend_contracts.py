"""Framework-free database ports and request-local constructor injection.

Scopes contain a caller-owned connection; they never open, commit or close it.
Overrides are trusted composition configuration, never accepted from HTTP input.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Any, Protocol, TypeVar


class Cursor(Protocol):
    rowcount: int

    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class DatabaseConnection(Protocol):
    def execute(self, query: str, params: Any = None) -> Cursor: ...
    def transaction(self) -> AbstractContextManager[Any]: ...
    def commit(self) -> None: ...


T = TypeVar("T")


class RepositoryScope:
    """One connection and cache per dependency scope, with cascading overrides."""

    def __init__(
        self,
        connection: DatabaseConnection,
        *,
        overrides: Mapping[type, Callable[..., Any]] | None = None,
        bindings: Mapping[type, Callable[..., Any]] | None = None,
    ):
        self.connection = connection
        self._bindings = dict(bindings or {})
        self._overrides = dict(overrides or {})
        for port, implementation in self._bindings.items():
            if port in self._overrides:
                self._overrides[implementation] = self._overrides[port]
        self._cache: dict[type, Any] = {}

    def resolve(self, port: type[T], **options: Any) -> T:
        implementation = self._bindings.get(port, port)
        if not options and implementation in self._cache:
            return self._cache[implementation]
        factory = self._overrides.get(port, self._overrides.get(implementation, implementation))
        kwargs = dict(options)
        if "repositories" in inspect.signature(factory).parameters:
            kwargs["repositories"] = self
        value = factory(self.connection, **kwargs)
        if not options:
            self._cache[implementation] = value
        return value
