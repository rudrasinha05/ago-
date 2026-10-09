"""Server-owned execution adapter registry with transactional approval claim.

No handlers are dynamically loaded from user input. Deployments, payments, email,
file deletion and similar side effects are not registered by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ago.security import Principal
from ago.workflows import GovernedTask


Handler = Callable[[GovernedTask], Any]


@dataclass(frozen=True)
class ExecutionOutcome:
    task_id: str
    success: bool
    result: Any = None


class GovernedExecutor:
    def __init__(self, task_store, *, handlers: dict[str, Handler] | None = None):
        self.task_store = task_store
        self._handlers = dict(handlers or {})

    def run(self, *, task_id: str, principal: Principal) -> ExecutionOutcome:
        """Claim exactly one approved task, then execute an allowlisted handler.

        Execution failures are recorded as terminal FAILED, not silently retried.
        External effects cannot be atomically rolled back: future adapters require
        their own idempotency and reconciliation designs.
        """
        task = self.task_store.authorize_and_start(task_id=task_id, principal=principal)
        handler = self._handlers.get(task.action)
        if handler is None:
            self.task_store.finish(
                task_id=task.id, tenant_id=task.tenant_id, success=False,
            )
            raise PermissionError("No trusted executor registered for approved action")
        try:
            result = handler(task)
        except Exception as exc:
            self.task_store.finish(
                task_id=task.id, tenant_id=task.tenant_id, success=False,
            )
            raise RuntimeError("Trusted action handler failed") from exc
        self.task_store.finish(
            task_id=task.id, tenant_id=task.tenant_id, success=True,
        )
        return ExecutionOutcome(task_id=task.id, success=True, result=result)
