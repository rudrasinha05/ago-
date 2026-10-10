"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class ExecutiveIntelligenceQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_governed_tasks_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT\n                (SELECT count(*) FROM ago_governed_tasks\n                   WHERE tenant_id=%s) AS total_tasks,\n                (SELECT count(*) FROM ago_governed_tasks\n                   WHERE tenant_id=%s AND status='completed') AS completed_tasks,\n                (SELECT count(*) FROM ago_governed_tasks\n                   WHERE tenant_id=%s AND status IN\n                     ('proposed','waiting_approval','ready','running')) AS backlog_tasks,\n                (SELECT count(*) FROM ago_task_reviews\n                   WHERE tenant_id=%s AND verdict='pass') AS qa_pass,\n                (SELECT count(*) FROM ago_approval_requests\n                   WHERE tenant_id=%s AND status='pending') AS pending_approvals,\n                (SELECT count(*) FROM ago_agent_runs\n                   WHERE tenant_id=%s AND status='failed') AS failed_agent_runs,\n                (SELECT count(*) FROM ago_handoffs\n                   WHERE tenant_id=%s AND status='requested') AS open_handoffs,\n                (SELECT count(*) FROM ago_knowledge_nodes\n                   WHERE tenant_id=%s AND status='verified') AS verified_knowledge,\n                (SELECT ceiling FROM ago_credit_budgets\n                   WHERE tenant_id=%s) AS budget_ceiling,\n                (SELECT consumed FROM ago_credit_budgets\n                   WHERE tenant_id=%s) AS budget_consumed,\n(SELECT count(*) FROM ago_goals WHERE tenant_id=%s) AS goals,\n              (SELECT count(*) FROM ago_strategy_plans WHERE tenant_id=%s) AS plans,\n              (SELECT coalesce(jsonb_agg(d), '[]'::jsonb) FROM\n                (SELECT x.id,x.name,count(t.id) AS assigned_tasks,\n                  count(t.id) FILTER (WHERE t.status IN\n                    ('proposed','waiting_approval','ready','running')) AS backlog\n                 FROM ago_departments x LEFT JOIN ago_employees e\n                   ON e.tenant_id=x.tenant_id AND e.department_id=x.id\n                 LEFT JOIN ago_governed_tasks t ON t.tenant_id=e.tenant_id AND t.assignee_id=e.id\n                 WHERE x.tenant_id=%s GROUP BY x.id,x.name ORDER BY x.id) d) AS departments,\n              (SELECT count(*) FROM ago_employees WHERE tenant_id=%s AND kind='ai') AS ai_employees,\n              (SELECT count(*) FROM ago_employees WHERE tenant_id=%s AND kind='human') AS human_employees,\n              (SELECT count(*) FROM ago_governed_tasks WHERE tenant_id=%s AND status='failed') AS failed_tasks",
            parameters,
        )

    def insert_ago_executive_snapshots_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_executive_snapshots\n                   (id,tenant_id,analyst_id,dna_id,metrics,risk_flags,fitness,digest)\n                   VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)",
            parameters,
        )

    def select_ago_executive_snapshots_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,analyst_id,dna_id,metrics,risk_flags,fitness,digest,created_at,capture_order\n               FROM ago_executive_snapshots WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def select_ago_executive_snapshots_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,dna_id,fitness,risk_flags,digest,created_at\n               FROM ago_executive_snapshots WHERE tenant_id=%s\n               ORDER BY capture_order DESC LIMIT %s",
            parameters,
        )

    def select_ago_dna_versions_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT profile FROM ago_dna_versions\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )
