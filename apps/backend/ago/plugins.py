"""M1.7 explicit plugin registry with dependency checks and lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Plugin(Protocol):
    name: str
    dependencies: tuple[str, ...]
    def start(self) -> None: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class PluginState:
    name: str
    running: bool


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._started: list[str] = []

    def register(self, plugin: Plugin) -> None:
        if not plugin.name or plugin.name in self._plugins:
            raise ValueError("Plugin name required and must be unique")
        if plugin.name in plugin.dependencies:
            raise ValueError("Plugin cannot depend on itself")
        self._plugins[plugin.name] = plugin

    def _order(self) -> list[str]:
        ordered: list[str] = []
        visiting: set[str] = set()
        def visit(name: str) -> None:
            if name in ordered:
                return
            if name in visiting:
                raise ValueError("Circular plugin dependency")
            if name not in self._plugins:
                raise ValueError(f"Missing plugin dependency: {name}")
            visiting.add(name)
            for dependency in self._plugins[name].dependencies:
                visit(dependency)
            visiting.remove(name)
            ordered.append(name)
        for name in self._plugins:
            visit(name)
        return ordered

    def start(self) -> None:
        try:
            for name in self._order():
                if name not in self._started:
                    self._plugins[name].start()
                    self._started.append(name)
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        errors: list[Exception] = []
        while self._started:
            name = self._started.pop()
            try:
                self._plugins[name].stop()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("Plugin shutdown failures", errors)

    def states(self) -> tuple[PluginState, ...]:
        return tuple(
            PluginState(name, name in self._started) for name in self._plugins
        )
