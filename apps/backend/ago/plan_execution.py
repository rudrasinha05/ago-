"""M3: activate approved strategies and materialize steps into governed tasks.

Materializing never authorizes actions. Every task requires a distinct M2 approval.
"""

from __future__ import annotations

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository
from ago.plan_execution_queries import PlanExecutionQueries
from ago.task_store import TaskStore


class PlanExecution:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def activate(self, *, tenant_id: str, plan_id: str) -> None:
        with self.db.transaction():
            plan = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_strategy_plans_01((tenant_id, plan_id))
                .fetchone()
            )
            if plan is None or plan["status"] != "pending_approval":
                raise PermissionError("Plan must await human approval")
            goal = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_goals_02((tenant_id, plan["goal_id"]))
                .fetchone()
            )
            if goal is None or goal["status"] != "active":
                raise PermissionError("Parent goal must still be active")
            self.repositories.resolve(ApprovalRepository).assert_executable(
                request_id=str(plan["approval_id"]),
                tenant_id=tenant_id,
                action=f"brain:activate:{plan_id}",
            )
            self.repositories.resolve(PlanExecutionQueries).update_ago_strategy_plans_03(
                (tenant_id, plan_id)
            )

    def materialize(self, *, tenant_id: str, plan_id: str) -> list[str]:
        with self.db.transaction():
            plan = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_strategy_plans_04((tenant_id, plan_id))
                .fetchone()
            )
            if plan is None or plan["status"] != "active" or plan["goal_status"] != "active":
                raise PermissionError("Only active approved plans may create tasks")
            rows = (
                self.repositories.resolve(PlanExecutionQueries)
                .select_ago_plan_steps_05((tenant_id, plan_id))
                .fetchall()
            )
            created = []
            for step in rows:
                if step["task_id"]:
                    created.append(str(step["task_id"]))
                    continue
                task = self.repositories.resolve(TaskStore).propose(
                    tenant_id=tenant_id,
                    action=step["action"],
                    assignee_id=str(step["assignee_id"]),
                )
                self.repositories.resolve(PlanExecutionQueries).update_ago_plan_steps_06(
                    (task.id, tenant_id, step["id"])
                )
                created.append(task.id)
        return created
