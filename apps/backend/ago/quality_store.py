"""Durable tenant-scoped independent QA review with immutable evidence."""
from __future__ import annotations

from uuid import UUID, uuid4

from ago.quality import Review, Verdict
from ago.security import Principal
from ago.security_controls import SecurityControls


class QualityStore:
    def __init__(self, connection):
        self.connection = connection

    def review(
        self, *, task_id: str, principal: Principal, verdict: Verdict,
        evidence: str,
    ) -> Review:
        UUID(task_id)
        UUID(principal.subject)
        UUID(principal.tenant_id)
        with self.connection.transaction():
            if not SecurityControls(self.connection).permitted(
                principal, "qa:review", principal.tenant_id
            ):
                raise PermissionError("QA permission required")
            task = self.connection.execute(
                """SELECT assignee_id, status FROM ago_governed_tasks
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (principal.tenant_id, task_id),
            ).fetchone()
            if task is None or task["status"] not in ("completed", "failed"):
                raise PermissionError("Only finished tasks may be reviewed")
            if verdict == Verdict.PASS and task["status"] != "completed":
                raise PermissionError("Failed tasks cannot receive passing QA")
            human = self.connection.execute(
                """SELECT 1 FROM ago_employees
                   WHERE tenant_id=%s AND id=%s AND kind='human'""",
                (principal.tenant_id, principal.subject),
            ).fetchone()
            if human is None:
                raise PermissionError("Independent human QA required")
            assessment = Review(
                tenant_id=principal.tenant_id, artifact_id=task_id,
                author_id=str(task["assignee_id"]), reviewer_id=principal.subject,
                verdict=verdict, evidence=evidence,
            )
            self.connection.execute(
                """INSERT INTO ago_task_reviews
                   (id, tenant_id, task_id, author_id, reviewer_id, verdict, evidence)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (str(uuid4()), assessment.tenant_id, assessment.artifact_id,
                 assessment.author_id, assessment.reviewer_id,
                 assessment.verdict.value, assessment.evidence),
            )
        return assessment

    def require_pass(self, *, task_id: str, tenant_id: str) -> None:
        row = self.connection.execute(
            """SELECT 1 FROM ago_task_reviews
               WHERE task_id=%s AND tenant_id=%s AND verdict='pass'""",
            (task_id, tenant_id),
        ).fetchone()
        if row is None:
            raise PermissionError("Independent QA pass not recorded")
