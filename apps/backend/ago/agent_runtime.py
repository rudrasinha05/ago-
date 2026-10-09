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
                self.db.execute(
                    """UPDATE ago_agent_runs SET status='completed',result=%s::jsonb,
                       finished_at=now() WHERE tenant_id=%s AND id=%s
                       AND status='running'""",
                    (payload, actor.tenant_id, run_id),
                )
                self.db.execute(
                    """INSERT INTO ago_agent_messages
                       (id,tenant_id,run_id,kind,content)
                       VALUES (%s,%s,%s,'evidence',%s)""",
                    (str(uuid4()), actor.tenant_id, run_id, "handler completed"),
                )
                TaskStore(self.db).finish(
                    task_id=task.id, tenant_id=actor.tenant_id, success=True,
                )
        except Exception as exc:
            with self.db.transaction():
                self.db.execute(
                    """UPDATE ago_agent_runs SET status='failed',
                       failure_code='handler_error',finished_at=now()
                       WHERE tenant_id=%s AND id=%s AND status='running'""",
                    (actor.tenant_id, run_id),
                )
                TaskStore(self.db).finish(
                    task_id=task.id, tenant_id=actor.tenant_id, success=False,
                )
            raise RuntimeError("Governed agent execution failed") from exc
        return {"id": run_id, "task_id": task.id, "status": "completed", "result": result}

    def recover_stale(self, *, tenant_id: str, minimum_age_seconds: int = 3600) -> int:
        """Mark abandoned runs failed; never auto-replay possible side effects."""
        UUID(tenant_id)
        if not 300 <= minimum_age_seconds <= 604800:
            raise ValueError("Stale-run threshold must be 5 minutes–7 days")
        with self.db.transaction():
            rows = self.db.execute(
                """SELECT r.id,r.task_id FROM ago_agent_runs r
                   WHERE r.tenant_id=%s AND r.status='running'
                     AND r.started_at < now() - (%s * interval '1 second')
                   ORDER BY r.started_at,r.id FOR UPDATE SKIP LOCKED LIMIT 100""",
                (tenant_id, minimum_age_seconds),
            ).fetchall()
            for row in rows:
                self.db.execute(
                    """UPDATE ago_agent_runs
                       SET status='failed',failure_code='worker_timeout',finished_at=now()
                       WHERE id=%s AND tenant_id=%s AND status='running'""",
                    (row["id"], tenant_id),
                )
                self.db.execute(
                    """UPDATE ago_governed_tasks
                       SET status='failed',updated_at=now()
                       WHERE id=%s AND tenant_id=%s AND status='running'""",
                    (row["task_id"], tenant_id),
                )
                self.db.execute(
                    """INSERT INTO ago_agent_messages
                       (id,tenant_id,run_id,kind,content)
                       VALUES (%s,%s,%s,'evidence',%s)""",
                    (str(uuid4()), tenant_id, row["id"],
                     "Worker timed out; manual reconciliation required"),
                )
        return len(rows)
