"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class DepartmentAutomationQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_employees_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT kind,department_id FROM ago_employees\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def insert_ago_automation_rules_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_automation_rules\n                   (id,tenant_id,creator_id,department_id,assignee_id,\n                    tool_code,trigger_kind)\n                   VALUES (%s,%s,%s,%s,%s,%s,%s)",
            parameters,
        )

    def update_ago_automation_rules_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_automation_rules SET status='disabled',\n                   disabled_at=now()\n                   WHERE tenant_id=%s AND id=%s AND status='active'\n                   RETURNING id",
            parameters,
        )

    def select_ago_automation_firings_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT 1 FROM ago_automation_firings\n                   WHERE tenant_id=%s AND task_id=%s",
            parameters,
        )

    def select_ago_governed_tasks_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT 1 FROM ago_governed_tasks t\n                   JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id\n                     AND q.task_id=t.id\n                   WHERE t.tenant_id=%s AND t.id=%s\n                     AND t.status='completed' AND q.verdict='pass'",
            parameters,
        )

    def select_ago_knowledge_nodes_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT 1 FROM ago_knowledge_nodes\n                   WHERE tenant_id=%s AND id=%s AND status='verified'",
            parameters,
        )

    def select_ago_automation_rules_07(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT creator_id,assignee_id,trigger_kind,tool_code,status\n                   FROM ago_automation_rules\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_automation_firings_08(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT task_id,approval_id,id FROM ago_automation_firings\n                   WHERE tenant_id=%s AND rule_id=%s AND source_id=%s",
            parameters,
        )

    def insert_ago_automation_firings_09(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_automation_firings\n                   (id,tenant_id,rule_id,source_id,task_id,approval_id)\n                   VALUES (%s,%s,%s,%s,%s,%s)",
            parameters,
        )

    def select_ago_automation_rules_10(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT r.id,r.trigger_kind FROM ago_automation_rules r\n               JOIN ago_tool_enrollments e ON e.tenant_id=r.tenant_id\n                 AND e.tool_code=r.tool_code AND e.status='active'\n               WHERE r.tenant_id=%s AND r.status='active'\n               ORDER BY r.created_at,r.id LIMIT 100",
            parameters,
        )

    def select_ago_governed_tasks_11(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT DISTINCT t.id AS source_id FROM ago_governed_tasks t\n                       JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id\n                         AND q.task_id=t.id\n                       WHERE t.tenant_id=%s AND t.status='completed'\n                         AND q.verdict='pass'\n                         AND NOT EXISTS (\n                           SELECT 1 FROM ago_automation_firings f\n                           WHERE f.tenant_id=t.tenant_id AND\n                             (f.task_id=t.id OR\n                              (f.rule_id=%s AND f.source_id=t.id)))\n                       ORDER BY source_id LIMIT %s",
            parameters,
        )

    def select_ago_knowledge_nodes_12(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT k.id AS source_id FROM ago_knowledge_nodes k\n                       WHERE k.tenant_id=%s AND k.status='verified'\n                         AND NOT EXISTS (\n                           SELECT 1 FROM ago_automation_firings f\n                           WHERE f.tenant_id=k.tenant_id AND f.rule_id=%s\n                             AND f.source_id=k.id)\n                       ORDER BY k.id LIMIT %s",
            parameters,
        )

    def select_ago_automation_rules_13(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,department_id,assignee_id,creator_id,tool_code,\n                      trigger_kind,status,created_at\n               FROM ago_automation_rules WHERE tenant_id=%s\n               ORDER BY created_at,id LIMIT 200",
            parameters,
        )

    def select_ago_automation_firings_14(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,rule_id,source_id,task_id,approval_id,created_at\n               FROM ago_automation_firings WHERE tenant_id=%s\n               ORDER BY created_at,id LIMIT 200",
            parameters,
        )
