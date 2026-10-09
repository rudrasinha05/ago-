"""Trusted, fail-closed orchestration boundary for M2.

No external side effects are performed here. The execution adapter must receive
only a task that passed this gate and must recheck authorization at execution.
"""
from __future__ import annotations

from dataclasses import dataclass

from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.workflows import GovernedTask, TaskStatus


@dataclass
class GovernanceGate:
    approvals: ApprovalRepository
    security: SecurityControls

    def decide(
        self, *, principal: Principal, request_id: str,
        tenant_id: str, approve: bool, reason: str,
    ):
        if principal.tenant_id != tenant_id:
            raise PermissionError("Cross-tenant decision denied")
        if not self.security.permitted(principal, "approval:decide", tenant_id):
            raise PermissionError("Reviewer lacks approval permission")
        return self.approvals.decide(
            request_id=request_id, tenant_id=tenant_id,
            reviewer_id=principal.subject, approve=approve,
            reason=reason, authorized=True,
        )

    def authorize_task(self, task: GovernedTask, *, principal: Principal) -> GovernedTask:
        if task.tenant_id != principal.tenant_id:
            raise PermissionError("Cross-tenant task denied")
        if not self.security.permitted(principal, "task:execute", task.tenant_id):
            raise PermissionError("Executor lacks task permission")
        if task.status != TaskStatus.WAITING_APPROVAL or not task.approval_id:
            raise PermissionError("Task has no pending approval reference")
        self.approvals.assert_executable(
            request_id=task.approval_id, tenant_id=task.tenant_id, action=task.action
        )
        return task.authorize(
            approved_request_id=task.approval_id,
            tenant_id=task.tenant_id, action=task.action,
        )
