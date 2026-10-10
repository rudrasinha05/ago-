"""M4: approved AI employee job runner; no implicit external tools."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from ago.agent_runtime_queries import AgentRuntimeQueries
from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.task_store import TaskStore


class AgentRuntime:
    def __init__(
        self, db: DatabaseConnection, *, handlers=None, repositories: RepositoryScope | None = None
    ):
        self.db = db
        self.handlers = dict(handlers or {})
        self.repositories = repositories or RepositoryScope(db)

    def run(self, *, task_id: str, actor) -> dict:
        UUID(task_id)
        with self.db.transaction():
            row = (
                self.repositories.resolve(AgentRuntimeQueries)
                .select_ago_governed_tasks_01((actor.tenant_id, task_id))
                .fetchone()
            )
            if row is None or row["action"] not in self.handlers:
                raise PermissionError("Task missing or handler not allowlisted")
            employee = (
                self.repositories.resolve(AgentRuntimeQueries)
                .select_ago_employees_02((actor.tenant_id, row["assignee_id"]))
                .fetchone()
            )
            if employee is None or employee["kind"] != "ai":
                raise PermissionError("Task requires an AI employee")
            task = self.repositories.resolve(TaskStore).authorize_and_start(
                task_id=task_id,
                principal=actor,
            )
            run_id = str(uuid4())
            self.repositories.resolve(AgentRuntimeQueries).insert_ago_agent_runs_03(
                (run_id, actor.tenant_id, task_id, row["assignee_id"], actor.subject)
            )
        return self._execute(run_id=run_id, task=task, actor=actor)

    def list(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid limit")
        return [
            dict(row)
            for row in self.repositories.resolve(AgentRuntimeQueries)
            .select_ago_agent_runs_04((tenant_id, limit))
            .fetchall()
        ]

    def _execute(self, *, run_id: str, task, actor) -> dict:
        """Store result or safe failure code. Never persist exception secrets."""
        try:
            result = self.handlers[task.action](task)
            if not isinstance(result, dict):
                raise ValueError("Agent result must be a dictionary")
            payload = json.dumps(result, allow_nan=False)
            if len(payload) > 32000:
                raise ValueError("Agent result exceeds size limit")
            with self.db.transaction():
                self.repositories.resolve(AgentRuntimeQueries).update_ago_agent_runs_05(
                    (payload, actor.tenant_id, run_id)
                )
                self.repositories.resolve(AgentRuntimeQueries).insert_ago_agent_messages_06(
                    (str(uuid4()), actor.tenant_id, run_id, "handler completed")
                )
                self.repositories.resolve(TaskStore).finish(
                    task_id=task.id,
                    tenant_id=actor.tenant_id,
                    success=True,
                )
        except Exception as exc:
            with self.db.transaction():
                self.repositories.resolve(AgentRuntimeQueries).update_ago_agent_runs_07(
                    (actor.tenant_id, run_id)
                )
                self.repositories.resolve(TaskStore).finish(
                    task_id=task.id,
                    tenant_id=actor.tenant_id,
                    success=False,
                )
            raise RuntimeError("Governed agent execution failed") from exc
        return {"id": run_id, "task_id": task.id, "status": "completed", "result": result}

    def recover_stale(self, *, tenant_id: str, minimum_age_seconds: int = 3600) -> int:
        """Mark abandoned runs failed; never auto-replay possible side effects."""
        UUID(tenant_id)
        if not 300 <= minimum_age_seconds <= 604800:
            raise ValueError("Stale-run threshold must be 5 minutes–7 days")
        with self.db.transaction():
            rows = (
                self.repositories.resolve(AgentRuntimeQueries)
                .select_ago_agent_runs_08((tenant_id, minimum_age_seconds))
                .fetchall()
            )
            for row in rows:
                self.repositories.resolve(AgentRuntimeQueries).update_ago_agent_runs_09(
                    (row["id"], tenant_id)
                )
                self.repositories.resolve(AgentRuntimeQueries).update_ago_governed_tasks_10(
                    (row["task_id"], tenant_id)
                )
                self.repositories.resolve(AgentRuntimeQueries).insert_ago_agent_messages_11(
                    (
                        str(uuid4()),
                        tenant_id,
                        row["id"],
                        "Worker timed out; manual reconciliation required",
                    )
                )
        return len(rows)
