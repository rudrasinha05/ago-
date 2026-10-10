"""M8 durable per-tenant enrollment for static, human-reviewed tools."""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.tool_catalog import require_tool_code
from ago.tool_enrollment_queries import ToolEnrollmentQueries


class ToolEnrollment:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _audit(
        self,
        *,
        actor: Principal,
        enrollment_id: str,
        event: str,
        rationale: str,
    ) -> None:
        self.repositories.resolve(ToolEnrollmentQueries).insert_ago_tool_enrollment_audit_01(
            (actor.tenant_id, enrollment_id, actor.subject, event, rationale)
        )

    def propose(self, *, actor: Principal, code: str, rationale: str) -> dict:
        require_tool_code(code)
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if not 1 <= len(rationale.strip()) <= 3000:
            raise ValueError("Enrolling a tool requires an explanation")
        with self.db.transaction():
            # Tenant row serializes proposals for exactly one live enrollment.
            owner = (
                self.repositories.resolve(ToolEnrollmentQueries)
                .select_ago_tenants_02((actor.tenant_id,))
                .fetchone()
            )
            if owner is None:
                raise LookupError("Tenant not found")
            current = (
                self.repositories.resolve(ToolEnrollmentQueries)
                .select_ago_tool_enrollments_03((actor.tenant_id, code))
                .fetchone()
            )
            if current is not None:
                raise PermissionError("An active or pending enrollment already exists")
            enrollment_id = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=actor.tenant_id,
                action=f"tool:enroll:{enrollment_id}",
                requester_id=actor.subject,
            )
            self.repositories.resolve(ToolEnrollmentQueries).insert_ago_tool_enrollments_04(
                (enrollment_id, actor.tenant_id, code, actor.subject, approval.request_id)
            )
            self._audit(
                actor=actor,
                enrollment_id=enrollment_id,
                event="proposed",
                rationale=rationale.strip(),
            )
        return {
            "id": enrollment_id,
            "tool_code": code,
            "approval_id": approval.request_id,
            "status": "proposed",
        }

    def reconcile(self, *, actor: Principal, enrollment_id: str) -> dict:
        UUID(enrollment_id)
        with self.db.transaction():
            row = (
                self.repositories.resolve(ToolEnrollmentQueries)
                .select_ago_tool_enrollments_05((actor.tenant_id, enrollment_id))
                .fetchone()
            )
            if row is None:
                raise LookupError("Tool enrollment not found")
            if row["status"] != "proposed":
                raise PermissionError("Tool enrollment already finalized")
            approval = (
                self.repositories.resolve(ToolEnrollmentQueries)
                .select_ago_approval_requests_06((actor.tenant_id, row["approval_id"]))
                .fetchone()
            )
            if approval is None or approval["action"] != f"tool:enroll:{enrollment_id}":
                raise PermissionError("Exact M2 tool authorization required")
            if approval["status"] == "approved":
                status = "active"
            elif approval["status"] == "rejected":
                status = "rejected"
            else:
                raise PermissionError("Independent human decision still pending")
            self.repositories.resolve(ToolEnrollmentQueries).update_ago_tool_enrollments_07(
                (status, actor.tenant_id, enrollment_id)
            )
            self._audit(
                actor=actor,
                enrollment_id=enrollment_id,
                event=status,
                rationale="Human M2 decision reconciled",
            )
        return {"id": enrollment_id, "tool_code": row["tool_code"], "status": status}

    def require_active(self, *, tenant_id: str, code: str) -> None:
        require_tool_code(code)
        row = (
            self.repositories.resolve(ToolEnrollmentQueries)
            .select_ago_tool_enrollments_08((tenant_id, code))
            .fetchone()
        )
        if row is None:
            raise PermissionError("Tenant has not activated this tool")

    def disable(
        self,
        *,
        actor: Principal,
        enrollment_id: str,
        reason: str,
    ) -> dict:
        UUID(enrollment_id)
        if not 1 <= len(reason.strip()) <= 3000:
            raise ValueError("Reason for disabling required")
        with self.db.transaction():
            row = (
                self.repositories.resolve(ToolEnrollmentQueries)
                .select_ago_tool_enrollments_09((actor.tenant_id, enrollment_id))
                .fetchone()
            )
            if row is None:
                raise LookupError("Tool enrollment not found")
            if row["status"] != "active":
                raise PermissionError("Only active tool enrollments can be disabled")
            self.repositories.resolve(ToolEnrollmentQueries).update_ago_tool_enrollments_10(
                (actor.tenant_id, enrollment_id)
            )
            self._audit(
                actor=actor,
                enrollment_id=enrollment_id,
                event="disabled",
                rationale=reason.strip(),
            )
        return {"id": enrollment_id, "status": "disabled"}

    def list(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.repositories.resolve(ToolEnrollmentQueries)
            .select_ago_tool_enrollments_11((tenant_id,))
            .fetchall()
        ]

    def history(self, *, tenant_id: str, enrollment_id: str) -> list[dict]:
        UUID(enrollment_id)
        return [
            dict(row)
            for row in self.repositories.resolve(ToolEnrollmentQueries)
            .select_ago_tool_enrollment_audit_12((tenant_id, enrollment_id))
            .fetchall()
        ]
