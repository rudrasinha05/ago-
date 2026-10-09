"""M2 governed task state machine. Execution is a separate trusted adapter."""
from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
from uuid import uuid4


class TaskStatus(str, Enum):
    PROPOSED = "proposed"
    WAITING_APPROVAL = "waiting_approval"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class GovernedTask:
    id: str
    tenant_id: str
    action: str
    assignee_id: str
    status: TaskStatus
    approval_id: str | None = None

    @classmethod
    def propose(cls, tenant_id: str, action: str, assignee_id: str) -> "GovernedTask":
        if not all((tenant_id.strip(), action.strip(), assignee_id.strip())):
            raise ValueError("Task fields required")
        return cls(str(uuid4()), tenant_id, action, assignee_id, TaskStatus.PROPOSED)

    def request_approval(self, approval_id: str) -> "GovernedTask":
        if self.status != TaskStatus.PROPOSED or not approval_id:
            raise ValueError("Invalid approval transition")
        return replace(self, status=TaskStatus.WAITING_APPROVAL, approval_id=approval_id)

    def authorize(self, *, approved_request_id: str, tenant_id: str, action: str) -> "GovernedTask":
        if (
            self.status != TaskStatus.WAITING_APPROVAL
            or not self.approval_id
            or approved_request_id != self.approval_id
            or tenant_id != self.tenant_id
            or action != self.action
        ):
            raise PermissionError("Verified scoped approval required")
        # Caller MUST verify the durable approval against trusted persistence.
        return replace(self, status=TaskStatus.READY)

    def start(self) -> "GovernedTask":
        if self.status != TaskStatus.READY:
            raise PermissionError("Task not authorized")
        return replace(self, status=TaskStatus.RUNNING)

    def finish(self, *, success: bool) -> "GovernedTask":
        if self.status != TaskStatus.RUNNING:
            raise ValueError("Task is not running")
        return replace(self, status=TaskStatus.COMPLETED if success else TaskStatus.FAILED)
