"""M2 governance foundation: deterministic, fail-closed human approval decisions.

This module evaluates approvals; execution adapters must enforce its decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    tenant_id: str
    action: str
    requester_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer_id: str | None = None
    reason: str | None = None

    @classmethod
    def propose(cls, *, tenant_id: str, action: str, requester_id: str) -> "ApprovalRequest":
        if not all((tenant_id.strip(), action.strip(), requester_id.strip())):
            raise ValueError("Tenant, action and requester are required")
        return cls(str(uuid4()), tenant_id, action, requester_id)

    def decide(
        self, *, reviewer_id: str, tenant_id: str, approve: bool, reason: str
    ) -> "ApprovalRequest":
        if tenant_id != self.tenant_id:
            raise PermissionError("Cross-tenant approval denied")
        if not reviewer_id.strip() or reviewer_id == self.requester_id:
            raise PermissionError("Independent reviewer required")
        if self.status != ApprovalStatus.PENDING:
            raise ValueError("Approval request already decided")
        if not reason.strip():
            raise ValueError("Decision reason required")
        return ApprovalRequest(
            request_id=self.request_id,
            tenant_id=self.tenant_id,
            action=self.action,
            requester_id=self.requester_id,
            status=ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED,
            reviewer_id=reviewer_id,
            reason=reason.strip(),
        )

    def assert_executable(self, *, tenant_id: str, action: str) -> None:
        if (
            tenant_id != self.tenant_id
            or action != self.action
            or self.status != ApprovalStatus.APPROVED
        ):
            raise PermissionError("Action is not approved for this tenant and scope")
