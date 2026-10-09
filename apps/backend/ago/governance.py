"""M2 governance: action policy and transactional PostgreSQL approvals.

Authorization of reviewers and execution must be enforced by the caller using
trusted, authenticated principals; never accept actor identity from untrusted input.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from ago.approvals import ApprovalRequest, ApprovalStatus


class Risk(str, Enum):
    LOW = "low"
    HIGH = "high"


class Constitution:
    """Conservative policy: unknown actions are high-risk."""

    HIGH_RISK_PREFIXES = (
        "deploy:", "spend:", "delete:", "external:", "access:", "publish:",
    )

    def classify(self, action: str) -> Risk:
        if not action or not action.strip():
            raise ValueError("Action required")
        # Unknown actions are not automatically safe.
        return Risk.HIGH

    def requires_approval(self, action: str) -> bool:
        return self.classify(action) == Risk.HIGH


@dataclass(frozen=True)
class Decision:
    request: ApprovalRequest


class ApprovalRepository:
    """Transactions guarantee a single terminal decision and matching audit entry.

    Expects a psycopg connection with dict_row row factory and autocommit=False.
    """

    def __init__(self, connection):
        self.connection = connection

    def propose(self, *, tenant_id: str, action: str, requester_id: str) -> ApprovalRequest:
        proposal = ApprovalRequest.propose(
            tenant_id=tenant_id, action=action, requester_id=requester_id
        )
        # Validate identifiers before executing SQL.
        for value in (tenant_id, requester_id):
            UUID(value)
        with self.connection.transaction():
            self.connection.execute(
                """INSERT INTO ago_approval_requests
                   (id, tenant_id, action, requester_id) VALUES (%s, %s, %s, %s)""",
                (proposal.request_id, tenant_id, action, requester_id),
            )
            self.connection.execute(
                """INSERT INTO ago_approval_audit
                   (request_id, tenant_id, actor_id, event)
                   VALUES (%s, %s, %s, 'proposed')""",
                (proposal.request_id, tenant_id, requester_id),
            )
        return proposal

    def decide(
        self, *, request_id: str, tenant_id: str, reviewer_id: str,
        approve: bool, reason: str, authorized: bool = False,
    ) -> ApprovalRequest:
        if not authorized:
            raise PermissionError("Reviewer authorization required")
        for value in (request_id, tenant_id, reviewer_id):
            UUID(value)
        with self.connection.transaction():
            row = self.connection.execute(
                """SELECT id, tenant_id, action, requester_id, status,
                          reviewer_id, reason
                   FROM ago_approval_requests WHERE id=%s AND tenant_id=%s
                   FOR UPDATE""",
                (request_id, tenant_id),
            ).fetchone()
            if row is None:
                raise LookupError("Approval not found")
            current = ApprovalRequest(
                request_id=str(row["id"]), tenant_id=str(row["tenant_id"]),
                action=row["action"], requester_id=str(row["requester_id"]),
                status=ApprovalStatus(row["status"]),
                reviewer_id=str(row["reviewer_id"]) if row["reviewer_id"] else None,
                reason=row["reason"],
            )
            decided = current.decide(
                reviewer_id=reviewer_id, tenant_id=tenant_id,
                approve=approve, reason=reason,
            )
            self.connection.execute(
                """UPDATE ago_approval_requests
                   SET status=%s, reviewer_id=%s, reason=%s, decided_at=now()
                   WHERE id=%s AND tenant_id=%s AND status='pending'""",
                (decided.status.value, reviewer_id, decided.reason, request_id, tenant_id),
            )
            self.connection.execute(
                """INSERT INTO ago_approval_audit
                   (request_id, tenant_id, actor_id, event, reason)
                   VALUES (%s, %s, %s, %s, %s)""",
                (request_id, tenant_id, reviewer_id, decided.status.value, decided.reason),
            )
        return decided

    def assert_executable(
        self, *, request_id: str, tenant_id: str, action: str
    ) -> None:
        row = self.connection.execute(
            """SELECT action, status FROM ago_approval_requests
               WHERE id=%s AND tenant_id=%s""",
            (request_id, tenant_id),
        ).fetchone()
        if row is None or row["action"] != action or row["status"] != "approved":
            raise PermissionError("Approved action not found for tenant and scope")
