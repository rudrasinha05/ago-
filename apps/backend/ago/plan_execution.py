"""M3: activate approved strategies and materialize steps into governed tasks.

Materializing never authorizes actions. Every task requires a distinct M2 approval.
"""
from __future__ import annotations

from ago.governance import ApprovalRepository
from ago.task_store import TaskStore


class PlanExecution:
    def __init__(self, db):
        self.db = db

    def activate(self, *, tenant_id: str, plan_id: str) -> None:
        with self.db.transaction():
            plan = self.db.execute(
                """SELECT status,approval_id,goal_id FROM ago_strategy_plans
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (tenant_id, plan_id),
            ).fetchone()
            if plan is None or plan["status"] != "pending_approval":
                raise PermissionError("Plan must await human approval")
            goal = self.db.execute(
                "SELECT status FROM ago_goals WHERE tenant_id=%s AND id=%s",
                (tenant_id, plan["goal_id"]),
            ).fetchone()
            if goal is None or goal["status"] != "active":
                raise PermissionError("Parent goal must still be active")
            ApprovalRepository(self.db).assert_executable(
                request_id=str(plan["approval_id"]), tenant_id=tenant_id,
                action=f"brain:activate:{plan_id}",
            )
            self.db.execute(
                """UPDATE ago_strategy_plans SET status='active',activated_at=now()
                   WHERE tenant_id=%s AND id=%s""",
                (tenant_id, plan_id),
            )

    def materialize(self, *, tenant_id: str, plan_id: str) -> list[str]:
        with self.db.transaction():
            plan = self.db.execute(
                """SELECT status FROM ago_strategy_plans
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (tenant_id, plan_id),
            ).fetchone()
            if plan is None or plan["status"] != "active":
                raise PermissionError("Only active approved plans may create tasks")
            rows = self.db.execute(
                """SELECT id,action,assignee_id,task_id FROM ago_plan_steps
                   WHERE tenant_id=%s AND plan_id=%s ORDER BY position""",
                (tenant_id, plan_id),
            ).fetchall()
            created = []
            for step in rows:
                if step["task_id"]:
                    created.append(str(step["task_id"]))
                    continue
                task = TaskStore(self.db).propose(
                    tenant_id=tenant_id, action=step["action"],
                    assignee_id=str(step["assignee_id"]),
                )
                self.db.execute(
                    """UPDATE ago_plan_steps SET task_id=%s
                       WHERE tenant_id=%s AND id=%s""",
                    (task.id, tenant_id, step["id"]),
                )
                created.append(task.id)
        return created
