"""M8 trusted tool execution. Approval claim is durable before a tool is invoked.

Task enrollment and per-task approval are separate independent human decisions.
Each task yields at most one run. Interrupted runs become 'uncertain' and require
manual reconciliation; AGO never blindly retries outside tools.
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from ago.security_controls import SecurityControls
from ago.task_store import TaskStore
from ago.tool_catalog import TOOL_CODES, handlers
from ago.tool_enrollment import ToolEnrollment


class EnterpriseToolRuntime:
    def __init__(self, db, *, trusted_handlers=None):
        self.db = db
        self._handlers = trusted_handlers

    def _evidence(self, *, tenant_id: str, run_id: str,
                  event: str, note: str) -> None:
        self.db.execute(
            """INSERT INTO ago_tool_run_evidence
               (tenant_id,run_id,event,note) VALUES (%s,%s,%s,%s)""",
            (tenant_id, run_id, event, note),
        )

    def run(self, *, task_id: str, actor) -> dict:
        UUID(task_id)
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if not SecurityControls(self.db).permitted(
            actor, "tool:dispatch", actor.tenant_id,
        ):
            raise PermissionError("Trusted tool dispatch permission required")
        # Never load arbitrary tool implementations from user data.
        registered = self._handlers if self._handlers is not None else handlers(self.db)
        with self.db.transaction():
            task_row = self.db.execute(
                """SELECT id,action,status FROM ago_governed_tasks
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, task_id),
            ).fetchone()
            if task_row is None:
                raise LookupError("Tool task not found")
            action = task_row["action"]
            if action not in TOOL_CODES or action not in registered:
                raise PermissionError("Unregistered tool action is forbidden")
            ToolEnrollment(self.db).require_active(
                tenant_id=actor.tenant_id, code=action,
            )
            exists = self.db.execute(
                """SELECT 1 FROM ago_tool_runs WHERE tenant_id=%s AND task_id=%s""",
                (actor.tenant_id, task_id),
            ).fetchone()
            if exists is not None:
                raise PermissionError("Tool runs are single-use; no replay")
            task = TaskStore(self.db).authorize_and_start(
                task_id=task_id, principal=actor,
            )
            run_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_tool_runs
                   (id,tenant_id,task_id,tool_code,executor_id)
                   VALUES (%s,%s,%s,%s,%s)""",
                (run_id, actor.tenant_id, task_id, action, actor.subject),
            )
            self._evidence(
                tenant_id=actor.tenant_id, run_id=run_id,
                event="claimed", note="Approved tenant tool task was claimed",
            )
        try:
            result = registered[action](task)
            if not isinstance(result, dict):
                raise ValueError("Tool must return a JSON object")
            payload = json.dumps(result, allow_nan=False)
            if len(payload.encode("utf-8")) > 32_000:
                raise ValueError("Enterprise tool output exceeds 32 KiB")
        except Exception as exc:
            with self.db.transaction():
                self.db.execute(
                    """UPDATE ago_tool_runs SET status='failed',
                       failure_code='handler_failed',finished_at=now()
                       WHERE tenant_id=%s AND id=%s AND status='running'""",
                    (actor.tenant_id, run_id),
                )
                self._evidence(
                    tenant_id=actor.tenant_id, run_id=run_id,
                    event="failed", note="Trusted handler failed; inspect before restart",
                )
                TaskStore(self.db).finish(
                    task_id=task.id, tenant_id=actor.tenant_id, success=False,
                )
            raise RuntimeError("Governed enterprise tool execution failed") from exc
        with self.db.transaction():
            self.db.execute(
                """UPDATE ago_tool_runs SET status='completed',
                   output=%s::jsonb,finished_at=now()
                   WHERE tenant_id=%s AND id=%s AND status='running'""",
                (payload, actor.tenant_id, run_id),
            )
            self._evidence(
                tenant_id=actor.tenant_id, run_id=run_id,
                event="completed", note="Read-only tool result captured for independent QA",
            )
            TaskStore(self.db).finish(
                task_id=task.id, tenant_id=actor.tenant_id, success=True,
            )
        return {
            "id": run_id, "task_id": task.id, "tool_code": action,
            "status": "completed", "result": result,
            "requires_independent_qa": True,
        }

    def recover_stale(
        self, *, tenant_id: str, minimum_age_seconds: int = 3600,
    ) -> int:
        UUID(tenant_id)
        if not 300 <= minimum_age_seconds <= 604800:
            raise ValueError("Recovery threshold must be 5 min–7 days")
        with self.db.transaction():
            rows = self.db.execute(
                """SELECT id,task_id FROM ago_tool_runs
                   WHERE tenant_id=%s AND status='running'
                     AND started_at < now() - (%s * interval '1 second')
                   ORDER BY started_at,id FOR UPDATE SKIP LOCKED LIMIT 100""",
                (tenant_id, minimum_age_seconds),
            ).fetchall()
            for row in rows:
                self.db.execute(
                    """UPDATE ago_tool_runs SET status='uncertain',
                       failure_code='worker_timeout',finished_at=now()
                       WHERE tenant_id=%s AND id=%s AND status='running'""",
                    (tenant_id, row["id"]),
                )
                self.db.execute(
                    """UPDATE ago_governed_tasks SET status='failed',updated_at=now()
                       WHERE tenant_id=%s AND id=%s AND status='running'""",
                    (tenant_id, row["task_id"]),
                )
                self._evidence(
                    tenant_id=tenant_id, run_id=str(row["id"]),
                    event="uncertain", note="Worker stopped; manual reconciliation required",
                )
        return len(rows)

    def list(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be 1–100")
        return [dict(row) for row in self.db.execute(
            """SELECT id,task_id,tool_code,executor_id,status,output,failure_code,
                      started_at,finished_at FROM ago_tool_runs
               WHERE tenant_id=%s ORDER BY started_at DESC,id LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()

    def evidence(self, *, tenant_id: str, run_id: str) -> list[dict]:
        UUID(run_id)
        return [dict(row) for row in self.db.execute(
            """SELECT event,note,created_at FROM ago_tool_run_evidence
               WHERE tenant_id=%s AND run_id=%s ORDER BY id LIMIT 100""",
            (tenant_id, run_id),
        ).fetchall()]
