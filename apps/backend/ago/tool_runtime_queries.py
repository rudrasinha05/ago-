"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class ToolRuntimeQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def insert_ago_tool_run_evidence_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_tool_run_evidence\n               (tenant_id,run_id,event,note) VALUES (%s,%s,%s,%s)",
            parameters,
        )

    def select_ago_governed_tasks_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,action,status FROM ago_governed_tasks\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_tool_runs_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT 1 FROM ago_tool_runs WHERE tenant_id=%s AND task_id=%s", parameters
        )

    def insert_ago_tool_runs_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_tool_runs\n                   (id,tenant_id,task_id,tool_code,executor_id)\n                   VALUES (%s,%s,%s,%s,%s)",
            parameters,
        )

    def update_ago_tool_runs_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_tool_runs SET status='failed',\n                       failure_code='handler_failed',finished_at=now()\n                       WHERE tenant_id=%s AND id=%s AND status='running'",
            parameters,
        )

    def update_ago_tool_runs_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_tool_runs SET status='completed',\n                   output=%s::jsonb,finished_at=now()\n                   WHERE tenant_id=%s AND id=%s AND status='running'",
            parameters,
        )

    def select_ago_tool_runs_07(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,task_id FROM ago_tool_runs\n                   WHERE tenant_id=%s AND status='running'\n                     AND started_at < now() - (%s * interval '1 second')\n                   ORDER BY started_at,id FOR UPDATE SKIP LOCKED LIMIT 100",
            parameters,
        )

    def update_ago_tool_runs_08(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_tool_runs SET status='uncertain',\n                       failure_code='worker_timeout',finished_at=now()\n                       WHERE tenant_id=%s AND id=%s AND status='running'",
            parameters,
        )

    def update_ago_governed_tasks_09(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_governed_tasks SET status='failed',updated_at=now()\n                       WHERE tenant_id=%s AND id=%s AND status='running'",
            parameters,
        )

    def select_ago_tool_runs_10(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,task_id,tool_code,executor_id,status,output,failure_code,\n                      started_at,finished_at FROM ago_tool_runs\n               WHERE tenant_id=%s ORDER BY started_at DESC,id LIMIT %s",
            parameters,
        )

    def select_ago_tool_run_evidence_11(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT event,note,created_at FROM ago_tool_run_evidence\n               WHERE tenant_id=%s AND run_id=%s ORDER BY id LIMIT 100",
            parameters,
        )
