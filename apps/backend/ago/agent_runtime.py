"""M4: approved AI employee job runner; no implicit external tools."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from ago.task_store import TaskStore


class AgentRuntime:
    def __init__(self, db, *, handlers=None):
        self.db = db
        self.handlers = dict(handlers or {})

    def run(self, *, task_id: str, actor) -> dict:
        UUID(task_id)
        with self.db.transaction():
            row = self.db.execute(
                """SELECT action,assignee_id FROM ago_governed_tasks
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, task_id),
            ).fetchone()
            if row is None or row["action"] not in self.handlers:
                raise PermissionError("Task missing or handler not allowlisted")
            employee = self.db.execute(
                """SELECT kind FROM ago_employees
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, row["assignee_id"]),
            ).fetchone()
            if employee is None or employee["kind"] != "ai":
                raise PermissionError("Task requires an AI employee")
            task = TaskStore(self.db).authorize_and_start(
                task_id=task_id, principal=actor,
            )
            run_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_agent_runs
                   (id,tenant_id,task_id,agent_id,executor_id,status)
                   VALUES (%s,%s,%s,%s,%s,'running')""",
                (run_id, actor.tenant_id, task_id, row["assignee_id"], actor.subject),
            )
        return self._execute(run_id=run_id, task=task, actor=actor)

    def list(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid limit")
        return [dict(row) for row in self.db.execute(
            """SELECT id,task_id,agent_id,status,result,failure_code,started_at
               FROM ago_agent_runs WHERE tenant_id=%s
               ORDER BY started_at DESC,id LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()]
