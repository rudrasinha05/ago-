"""Configuration, contextual logging, and dependency injection fundamentals."""
from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGO_", extra="ignore")
    environment: str = "development"
    service_name: str = "ago-backend"
    log_level: str = "INFO"


request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get() or "-"
        return True


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Unsupported log level: {settings.log_level}")
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
    ))
    logging.basicConfig(level=level, handlers=[handler], force=True)


class Lifetime(str, Enum):
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


class DependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Registration:
    factory: Callable[["Resolver"], Any]
    lifetime: Lifetime


class Resolver:
    def __init__(self, container: "Container", cache: dict[str, Any], stack: ExitStack | None = None):
        self._container = container
        self._cache = cache
        self._stack = stack
        self._resolving: set[str] = set()

    def resolve(self, name: str) -> Any:
        if name in self._resolving:
            raise DependencyError(f"Circular dependency: {name}")
        registration = self._container._registrations.get(name)
        if registration is None:
            raise DependencyError(f"Dependency not registered: {name}")
        cache = (self._container._singletons if registration.lifetime is Lifetime.SINGLETON
                 else self._cache if registration.lifetime is Lifetime.SCOPED else None)
        if cache is not None and name in cache:
            return cache[name]
        self._resolving.add(name)
        try:
            instance = registration.factory(self)
            if self._stack is not None and hasattr(instance, "__enter__") and hasattr(instance, "__exit__"):
                instance = self._stack.enter_context(instance)
        finally:
            self._resolving.remove(name)
        if cache is not None:
            cache[name] = instance
        return instance


class Container:
    def __init__(self) -> None:
        self._registrations: dict[str, Registration] = {}
        self._singletons: dict[str, Any] = {}
        self._closed = False

    def register(self, name: str, factory: Callable[[Resolver], Any],
                 lifetime: Lifetime = Lifetime.TRANSIENT) -> None:
        if self._closed:
            raise DependencyError("Container is closed")
        if name in self._registrations:
            raise DependencyError(f"Duplicate registration: {name}")
        self._registrations[name] = Registration(factory, lifetime)

    def resolve(self, name: str) -> Any:
        if self._closed:
            raise DependencyError("Container is closed")
        return Resolver(self, {}).resolve(name)

    def validate(self, required: tuple[str, ...] = ()) -> None:
        """Validate explicitly required services before startup."""
        missing = [name for name in required if name not in self._registrations]
        if missing:
            raise DependencyError(f"Missing required registrations: {missing}")

    def close(self) -> None:
        self._singletons.clear()
        self._closed = True

    @contextmanager
    def scope(self):
        if self._closed:
            raise DependencyError("Container is closed")
        with ExitStack() as stack:
            yield Resolver(self, {}, stack)


def build_container(settings: Settings | None = None) -> Container:
    container = Container()
    container.register("settings", lambda _: settings or Settings(), Lifetime.SINGLETON)
    container.register("logger", lambda _: logging.getLogger("ago"), Lifetime.SINGLETON)
    return container
