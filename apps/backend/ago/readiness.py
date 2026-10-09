"""M1.9 readiness checks with explicit dependency reporting."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    healthy: bool
    detail: str


class ReadinessChecks:
    def __init__(self):
        self._checks: dict[str, Callable[[], bool]] = {}

    def register(self, name: str, check: Callable[[], bool]) -> None:
        if not name or name in self._checks:
            raise ValueError("Check name required and must be unique")
        self._checks[name] = check

    def run(self) -> tuple[CheckResult, ...]:
        results = []
        for name, check in self._checks.items():
            try:
                healthy = bool(check())
                results.append(CheckResult(name, healthy, "ok" if healthy else "unavailable"))
            except Exception:
                results.append(CheckResult(name, False, "check_failed"))
        return tuple(results)

    def ready(self) -> bool:
        results = self.run()
        return bool(results) and all(item.healthy for item in results)
