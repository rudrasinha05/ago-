"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class ScorecardQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_tenant_count_01(self, parameters: Any = None, *, table: str) -> Cursor:
        if table not in (
            "ago_agent_runs",
            "ago_automation_firings",
            "ago_automation_rules",
            "ago_calendar_events",
            "ago_council_motions",
            "ago_dna_versions",
            "ago_executive_snapshots",
            "ago_goals",
            "ago_governed_tasks",
            "ago_handoffs",
            "ago_knowledge_nodes",
            "ago_meta_recommendations",
            "ago_policy_experiments",
            "ago_strategy_plans",
            "ago_task_reviews",
            "ago_tool_enrollments",
            "ago_tool_runs",
        ):
            raise ValueError("Unapproved static query selector")
        return self.connection.execute(
            f"SELECT count(*) AS total FROM {table} WHERE tenant_id=%s", parameters
        )

    def select_ago_governed_tasks_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status,count(*) AS total FROM ago_governed_tasks\n               WHERE tenant_id=%s GROUP BY status",
            parameters,
        )
