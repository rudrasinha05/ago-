"""M2 governance: action policy and transactional PostgreSQL approvals.

Authorization of reviewers and execution must be enforced by the caller using
trusted, authenticated principals; never accept actor identity from untrusted input.
"""

from __future__ import annotations

from uuid import UUID

from ago.approvals import ApprovalRequest, ApprovalStatus
from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance_domain import Constitution as Constitution
from ago.governance_domain import Decision as Decision
from ago.governance_domain import Risk as Risk


class ApprovalRepository:
    """Transactions guarantee a single terminal decision and matching audit entry.

    Expects a psycopg connection with dict_row row factory and autocommit=False.
    """

    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

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
        self,
        *,
        request_id: str,
        tenant_id: str,
        reviewer_id: str,
        approve: bool,
        reason: str,
        authorized: bool = False,
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
                request_id=str(row["id"]),
                tenant_id=str(row["tenant_id"]),
                action=row["action"],
                requester_id=str(row["requester_id"]),
                status=ApprovalStatus(row["status"]),
                reviewer_id=str(row["reviewer_id"]) if row["reviewer_id"] else None,
                reason=row["reason"],
            )
            human = self.connection.execute(
                """SELECT 1 FROM ago_users u JOIN ago_employees e
                     ON e.id=u.id AND e.tenant_id=u.tenant_id
                   WHERE u.id=%s AND u.tenant_id=%s AND u.active=true
                     AND e.kind='human'""",
                (reviewer_id, tenant_id),
            ).fetchone()
            if human is None:
                raise PermissionError("Active human reviewer required")
            decided = current.decide(
                reviewer_id=reviewer_id,
                tenant_id=tenant_id,
                approve=approve,
                reason=reason,
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

    def list_requests(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid approval list limit")
        rows = self.connection.execute(
            """SELECT id, action, requester_id, reviewer_id, status, reason, created_at
               FROM ago_approval_requests WHERE tenant_id=%s
               ORDER BY created_at DESC, id LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def assert_executable(self, *, request_id: str, tenant_id: str, action: str) -> None:
        row = self.connection.execute(
            """SELECT action, status FROM ago_approval_requests
               WHERE id=%s AND tenant_id=%s""",
            (request_id, tenant_id),
        ).fetchone()
        if row is None or row["action"] != action or row["status"] != "approved":
            raise PermissionError("Approved action not found for tenant and scope")
