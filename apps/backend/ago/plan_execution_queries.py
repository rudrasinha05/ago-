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

    def select_founder_stage_step_07(self, parameters: Any = None) -> Cursor:
        """(stage, tenant_id, project_id, founder_id): lock the stage and its goal."""
        return self.connection.execute(
            """SELECT ps.id AS plan_step_id,ps.plan_id,ps.action,ps.assignee_id,ps.task_id,
                      p.status AS plan_status,g.status AS goal_status
               FROM ago_founder_intakes i
               JOIN ago_founder_intake_stages s ON s.tenant_id=i.tenant_id
                AND s.intake_id=i.id AND s.stage=%s
               JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id
                AND ps.plan_id=s.plan_id AND ps.id=s.plan_step_id
               JOIN ago_strategy_plans p ON p.tenant_id=ps.tenant_id AND p.id=ps.plan_id
               JOIN ago_goals g ON g.tenant_id=p.tenant_id AND g.id=p.goal_id
               WHERE i.tenant_id=%s AND i.id=%s AND i.founder_id=%s
               FOR UPDATE OF ps,g""",
            parameters,
        )

    def select_task_for_recovery_08(self, parameters: Any = None) -> Cursor:
        """(tenant_id, task_id): task status plus whether any run is still running."""
        return self.connection.execute(
            """SELECT t.status,t.action,t.assignee_id,
                      EXISTS (SELECT 1 FROM ago_agent_runs r
                              WHERE r.tenant_id=t.tenant_id AND r.task_id=t.id
                                AND r.status='running') AS run_active,
                      EXISTS (SELECT 1 FROM ago_plan_step_task_recoveries v
                              WHERE v.tenant_id=t.tenant_id AND v.failed_task_id=t.id)
                        AS already_recovered
               FROM ago_governed_tasks t
               WHERE t.tenant_id=%s AND t.id=%s FOR UPDATE OF t""",
            parameters,
        )

    def insert_step_task_recovery_09(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            """INSERT INTO ago_plan_step_task_recoveries
               (tenant_id,plan_id,plan_step_id,failed_task_id,recovery_task_id,actor_id,reason)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,created_at""",
            parameters,
        )

    def relink_step_task_10(self, parameters: Any = None) -> Cursor:
        """(recovery_task_id, tenant_id, plan_step_id, failed_task_id); trigger-guarded."""
        return self.connection.execute(
            """UPDATE ago_plan_steps SET task_id=%s
               WHERE tenant_id=%s AND id=%s AND task_id=%s""",
            parameters,
        )
