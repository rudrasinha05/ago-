"""M8 trusted tool execution. Approval claim is durable before a tool is invoked.

Task enrollment and per-task approval are separate independent human decisions.
Each task yields at most one run. Interrupted runs become 'uncertain' and require
manual reconciliation; AGO never blindly retries outside tools.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore
from ago.tool_catalog import TOOL_CODES, handlers
from ago.tool_enrollment import ToolEnrollment
from ago.tool_runtime_queries import ToolRuntimeQueries


class EnterpriseToolRuntime:
    def __init__(
        self,
        db: DatabaseConnection,
        *,
        trusted_handlers=None,
        repositories: RepositoryScope | None = None,
    ):
        self.db = db
        self._handlers = trusted_handlers
        self.repositories = repositories or RepositoryScope(db)

    def _evidence(self, *, tenant_id: str, run_id: str, event: str, note: str) -> None:
        self.repositories.resolve(ToolRuntimeQueries).insert_ago_tool_run_evidence_01(
            (tenant_id, run_id, event, note)
        )

    def run(self, *, task_id: str, actor) -> dict:
        UUID(task_id)
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if not self.repositories.resolve(SecurityControls).permitted(
            actor,
            "tool:dispatch",
            actor.tenant_id,
        ):
            raise PermissionError("Trusted tool dispatch permission required")
        # Never load arbitrary tool implementations from user data.
        registered = (
            self._handlers
            if self._handlers is not None
            else handlers(self.db, repositories=self.repositories)
        )
        with self.db.transaction():
            task_row = (
                self.repositories.resolve(ToolRuntimeQueries)
                .select_ago_governed_tasks_02((actor.tenant_id, task_id))
                .fetchone()
            )
            if task_row is None:
                raise LookupError("Tool task not found")
            action = task_row["action"]
            if action not in TOOL_CODES or action not in registered:
                raise PermissionError("Unregistered tool action is forbidden")
            self.repositories.resolve(ToolEnrollment).require_active(
                tenant_id=actor.tenant_id,
                code=action,
            )
            exists = (
                self.repositories.resolve(ToolRuntimeQueries)
                .select_ago_tool_runs_03((actor.tenant_id, task_id))
                .fetchone()
            )
            if exists is not None:
                raise PermissionError("Tool runs are single-use; no replay")
            task = self.repositories.resolve(TaskStore).authorize_and_start(
                task_id=task_id,
                principal=actor,
            )
            run_id = str(uuid4())
            self.repositories.resolve(ToolRuntimeQueries).insert_ago_tool_runs_04(
                (run_id, actor.tenant_id, task_id, action, actor.subject)
            )
            self._evidence(
                tenant_id=actor.tenant_id,
                run_id=run_id,
                event="claimed",
                note="Approved tenant tool task was claimed",
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
                self.repositories.resolve(ToolRuntimeQueries).update_ago_tool_runs_05(
                    (actor.tenant_id, run_id)
                )
                self._evidence(
                    tenant_id=actor.tenant_id,
                    run_id=run_id,
                    event="failed",
                    note="Trusted handler failed; inspect before restart",
                )
                self.repositories.resolve(TaskStore).finish(
                    task_id=task.id,
                    tenant_id=actor.tenant_id,
                    success=False,
                )
            raise RuntimeError("Governed enterprise tool execution failed") from exc
        with self.db.transaction():
            self.repositories.resolve(ToolRuntimeQueries).update_ago_tool_runs_06(
                (payload, actor.tenant_id, run_id)
            )
            self._evidence(
                tenant_id=actor.tenant_id,
                run_id=run_id,
                event="completed",
                note="Read-only tool result captured for independent QA",
            )
            self.repositories.resolve(TaskStore).finish(
                task_id=task.id,
                tenant_id=actor.tenant_id,
                success=True,
            )
        return {
            "id": run_id,
            "task_id": task.id,
            "tool_code": action,
            "status": "completed",
            "result": result,
            "requires_independent_qa": True,
        }

    def recover_stale(
        self,
        *,
        tenant_id: str,
        minimum_age_seconds: int = 3600,
    ) -> int:
        UUID(tenant_id)
        if not 300 <= minimum_age_seconds <= 604800:
            raise ValueError("Recovery threshold must be 5 min–7 days")
        with self.db.transaction():
            rows = (
                self.repositories.resolve(ToolRuntimeQueries)
                .select_ago_tool_runs_07((tenant_id, minimum_age_seconds))
                .fetchall()
            )
            for row in rows:
                self.repositories.resolve(ToolRuntimeQueries).update_ago_tool_runs_08(
                    (tenant_id, row["id"])
                )
                self.repositories.resolve(ToolRuntimeQueries).update_ago_governed_tasks_09(
                    (tenant_id, row["task_id"])
                )
                self._evidence(
                    tenant_id=tenant_id,
                    run_id=str(row["id"]),
                    event="uncertain",
                    note="Worker stopped; manual reconciliation required",
                )
        return len(rows)

    def list(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be 1–100")
        return [
            dict(row)
            for row in self.repositories.resolve(ToolRuntimeQueries)
            .select_ago_tool_runs_10((tenant_id, limit))
            .fetchall()
        ]

    def evidence(self, *, tenant_id: str, run_id: str) -> list[dict]:
        UUID(run_id)
        return [
            dict(row)
            for row in self.repositories.resolve(ToolRuntimeQueries)
            .select_ago_tool_run_evidence_11((tenant_id, run_id))
            .fetchall()
        ]
