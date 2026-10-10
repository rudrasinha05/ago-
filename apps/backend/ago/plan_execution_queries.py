"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class PlanExecutionQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_strategy_plans_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status,approval_id,goal_id FROM ago_strategy_plans\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_goals_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status FROM ago_goals WHERE tenant_id=%s AND id=%s", parameters
        )

    def update_ago_strategy_plans_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_strategy_plans SET status='active',activated_at=now()\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def select_ago_strategy_plans_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT p.status,g.status AS goal_status\n                   FROM ago_strategy_plans p JOIN ago_goals g\n                     ON g.tenant_id=p.tenant_id AND g.id=p.goal_id\n                   WHERE p.tenant_id=%s AND p.id=%s FOR UPDATE OF p",
            parameters,
        )

    def select_ago_plan_steps_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,action,assignee_id,task_id FROM ago_plan_steps\n                   WHERE tenant_id=%s AND plan_id=%s ORDER BY position",
            parameters,
        )

    def update_ago_plan_steps_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_plan_steps SET task_id=%s\n                       WHERE tenant_id=%s AND id=%s",
            parameters,
        )
