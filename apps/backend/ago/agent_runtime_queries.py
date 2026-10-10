"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class AgentRuntimeQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_governed_tasks_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT action,assignee_id FROM ago_governed_tasks\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_employees_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT kind FROM ago_employees\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def insert_ago_agent_runs_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_agent_runs\n                   (id,tenant_id,task_id,agent_id,executor_id,status,dna_context)\n                   VALUES (%s,%s,%s,%s,%s,'running',%s::jsonb)",
            parameters,
        )

    def select_ago_agent_runs_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,task_id,agent_id,status,result,failure_code,started_at,dna_context\n               FROM ago_agent_runs WHERE tenant_id=%s\n               ORDER BY started_at DESC,id LIMIT %s",
            parameters,
        )

    def update_ago_agent_runs_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_agent_runs SET status='completed',result=%s::jsonb,\n                       finished_at=now() WHERE tenant_id=%s AND id=%s\n                       AND status='running'",
            parameters,
        )

    def insert_ago_agent_messages_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_agent_messages\n                       (id,tenant_id,run_id,kind,content)\n                       VALUES (%s,%s,%s,'evidence',%s)",
            parameters,
        )

    def update_ago_agent_runs_07(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_agent_runs SET status='failed',\n                       failure_code='handler_error',finished_at=now()\n                       WHERE tenant_id=%s AND id=%s AND status='running'",
            parameters,
        )

    def select_ago_agent_runs_08(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT r.id,r.task_id FROM ago_agent_runs r\n                   WHERE r.tenant_id=%s AND r.status='running'\n                     AND r.started_at < now() - (%s * interval '1 second')\n                   ORDER BY r.started_at,r.id FOR UPDATE SKIP LOCKED LIMIT 100",
            parameters,
        )

    def update_ago_agent_runs_09(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_agent_runs\n                       SET status='failed',failure_code='worker_timeout',finished_at=now()\n                       WHERE id=%s AND tenant_id=%s AND status='running'",
            parameters,
        )

    def update_ago_governed_tasks_10(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_governed_tasks\n                       SET status='failed',updated_at=now()\n                       WHERE id=%s AND tenant_id=%s AND status='running'",
            parameters,
        )

    def insert_ago_agent_messages_11(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_agent_messages\n                       (id,tenant_id,run_id,kind,content)\n                       VALUES (%s,%s,%s,'evidence',%s)",
            parameters,
        )
