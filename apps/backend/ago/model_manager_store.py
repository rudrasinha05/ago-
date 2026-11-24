"""Workforce Manager model-choice persistence (MGR-002); caller owns the transaction."""
from __future__ import annotations

from uuid import uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope


class ModelManagerStore:
    def __init__(self, connection: DatabaseConnection, *,
                 repositories: RepositoryScope | None = None):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def builder_results(self, tenant_id: str) -> dict[str, dict]:
        """Per model that wrote a stage deliverable: how its work did in QA."""
        rows = self.connection.execute(
            """SELECT r.result->'handoffs'->-1->>'model' AS model,
                      count(*) FILTER (WHERE q.verdict='pass') AS passed,
                      count(*) FILTER (WHERE q.verdict='fail') AS failed
               FROM ago_agent_runs r
               JOIN ago_task_reviews q ON q.tenant_id=r.tenant_id AND q.task_id=r.task_id
               WHERE r.tenant_id=%s AND jsonb_typeof(r.result->'handoffs')='array'
               GROUP BY 1""", (tenant_id,)).fetchall()
        return {r["model"]: {"passed": r["passed"], "failed": r["failed"]}
                for r in rows if r["model"]}

    def stage_failed_before(self, tenant_id: str, project_id: str, stage: str) -> bool:
        """True when this project stage was already sent back by QA or put on hold."""
        return self.connection.execute(
            """SELECT 1 FROM ago_project_followups
               WHERE tenant_id=%s AND project_id=%s AND stage=%s
                 AND code IN ('qa_rework','recovery_limit_reached') LIMIT 1""",
            (tenant_id, project_id, stage)).fetchone() is not None

    def record(self, tenant_id: str, task_id: str | None, work: str, role: str | None,
               model_label: str, reason: str) -> None:
        self.connection.execute(
            """INSERT INTO ago_model_decisions(id,tenant_id,task_id,work,role,model_label,reason)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (str(uuid4()), tenant_id, task_id, work, role, model_label[:200], reason[:600]))

    def recent(self, tenant_id: str, limit: int = 30) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT id,task_id,work,role,model_label,reason,created_at FROM ago_model_decisions
               WHERE tenant_id=%s ORDER BY created_at DESC LIMIT %s""",
            (tenant_id, limit)).fetchall()]
