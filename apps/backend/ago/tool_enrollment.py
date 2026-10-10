"""M8 durable per-tenant enrollment for static, human-reviewed tools."""
from __future__ import annotations

from uuid import UUID, uuid4

from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.tool_catalog import require_tool_code


class ToolEnrollment:
    def __init__(self, db):
        self.db = db

    def _audit(
        self, *, actor: Principal, enrollment_id: str,
        event: str, rationale: str,
    ) -> None:
        self.db.execute(
            """INSERT INTO ago_tool_enrollment_audit
               (tenant_id,enrollment_id,actor_id,event,rationale)
               VALUES (%s,%s,%s,%s,%s)""",
            (actor.tenant_id, enrollment_id, actor.subject, event, rationale),
        )

    def propose(self, *, actor: Principal, code: str, rationale: str) -> dict:
        require_tool_code(code)
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if not 1 <= len(rationale.strip()) <= 3000:
            raise ValueError("Enrolling a tool requires an explanation")
        with self.db.transaction():
            # Tenant row serializes proposals for exactly one live enrollment.
            owner = self.db.execute(
                "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE",
                (actor.tenant_id,),
            ).fetchone()
            if owner is None:
                raise LookupError("Tenant not found")
            current = self.db.execute(
                """SELECT id,status FROM ago_tool_enrollments
                   WHERE tenant_id=%s AND tool_code=%s
                     AND status IN ('proposed','active')""",
                (actor.tenant_id, code),
            ).fetchone()
            if current is not None:
                raise PermissionError("An active or pending enrollment already exists")
            enrollment_id = str(uuid4())
            approval = ApprovalRepository(self.db).propose(
                tenant_id=actor.tenant_id,
                action=f"tool:enroll:{enrollment_id}",
                requester_id=actor.subject,
            )
            self.db.execute(
                """INSERT INTO ago_tool_enrollments
                   (id,tenant_id,tool_code,proposer_id,approval_id)
                   VALUES (%s,%s,%s,%s,%s)""",
                (enrollment_id, actor.tenant_id, code,
                 actor.subject, approval.request_id),
            )
            self._audit(
                actor=actor, enrollment_id=enrollment_id,
                event="proposed", rationale=rationale.strip(),
            )
        return {
            "id": enrollment_id, "tool_code": code,
            "approval_id": approval.request_id, "status": "proposed",
        }

    def reconcile(self, *, actor: Principal, enrollment_id: str) -> dict:
        UUID(enrollment_id)
        with self.db.transaction():
            row = self.db.execute(
                """SELECT status,approval_id,tool_code FROM ago_tool_enrollments
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, enrollment_id),
            ).fetchone()
            if row is None:
                raise LookupError("Tool enrollment not found")
            if row["status"] != "proposed":
                raise PermissionError("Tool enrollment already finalized")
            approval = self.db.execute(
                """SELECT status,action FROM ago_approval_requests
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, row["approval_id"]),
            ).fetchone()
            if (approval is None or
                    approval["action"] != f"tool:enroll:{enrollment_id}"):
                raise PermissionError("Exact M2 tool authorization required")
            if approval["status"] == "approved":
                status = "active"
            elif approval["status"] == "rejected":
                status = "rejected"
            else:
                raise PermissionError("Independent human decision still pending")
            self.db.execute(
                """UPDATE ago_tool_enrollments
                   SET status=%s,changed_at=now()
                   WHERE tenant_id=%s AND id=%s""",
                (status, actor.tenant_id, enrollment_id),
            )
            self._audit(
                actor=actor, enrollment_id=enrollment_id,
                event=status, rationale="Human M2 decision reconciled",
            )
        return {"id": enrollment_id, "tool_code": row["tool_code"],
                "status": status}

    def require_active(self, *, tenant_id: str, code: str) -> None:
        require_tool_code(code)
        row = self.db.execute(
            """SELECT 1 FROM ago_tool_enrollments
               WHERE tenant_id=%s AND tool_code=%s AND status='active'""",
            (tenant_id, code),
        ).fetchone()
        if row is None:
            raise PermissionError("Tenant has not activated this tool")

    def disable(
        self, *, actor: Principal, enrollment_id: str, reason: str,
    ) -> dict:
        UUID(enrollment_id)
        if not 1 <= len(reason.strip()) <= 3000:
            raise ValueError("Reason for disabling required")
        with self.db.transaction():
            row = self.db.execute(
                """SELECT status FROM ago_tool_enrollments
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, enrollment_id),
            ).fetchone()
            if row is None:
                raise LookupError("Tool enrollment not found")
            if row["status"] != "active":
                raise PermissionError("Only active tool enrollments can be disabled")
            self.db.execute(
                """UPDATE ago_tool_enrollments SET status='disabled',changed_at=now()
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, enrollment_id),
            )
            self._audit(
                actor=actor, enrollment_id=enrollment_id,
                event="disabled", rationale=reason.strip(),
            )
        return {"id": enrollment_id, "status": "disabled"}

    def list(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            """SELECT id,tool_code,proposer_id,approval_id,status,created_at,changed_at
               FROM ago_tool_enrollments WHERE tenant_id=%s
               ORDER BY created_at DESC,id LIMIT 200""",
            (tenant_id,),
        ).fetchall()]

    def history(self, *, tenant_id: str, enrollment_id: str) -> list[dict]:
        UUID(enrollment_id)
        return [dict(row) for row in self.db.execute(
            """SELECT actor_id,event,rationale,created_at
               FROM ago_tool_enrollment_audit
               WHERE tenant_id=%s AND enrollment_id=%s
               ORDER BY id LIMIT 200""",
            (tenant_id, enrollment_id),
        ).fetchall()]
