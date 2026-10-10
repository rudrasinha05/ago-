"""M3: tenant-scoped, immutable-after-submission strategic action plans."""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository


class PlanStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def create(self, *, tenant_id: str, proposer_id: str, goal_id: str, title: str) -> str:
        for value in (tenant_id, proposer_id, goal_id):
            UUID(value)
        if not title.strip() or len(title) > 250:
            raise ValueError("Invalid plan title")
        with self.db.transaction():
            goal = self.db.execute(
                "SELECT status FROM ago_goals WHERE tenant_id=%s AND id=%s",
                (tenant_id, goal_id),
            ).fetchone()
            if goal is None or goal["status"] != "active":
                raise PermissionError("Active goal required")
            plan_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_strategy_plans
                   (id,tenant_id,goal_id,proposer_id,title)
                   VALUES (%s,%s,%s,%s,%s)""",
                (plan_id, tenant_id, goal_id, proposer_id, title.strip()),
            )
        return plan_id

    def add_step(
        self,
        *,
        tenant_id: str,
        plan_id: str,
        action: str,
        assignee_id: str,
        depends_on: str | None = None,
    ) -> str:
        for value in (tenant_id, plan_id, assignee_id):
            UUID(value)
        if not action.strip() or len(action) > 500:
            raise ValueError("Invalid step action")
        with self.db.transaction():
            plan = self.db.execute(
                """SELECT status FROM ago_strategy_plans
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (tenant_id, plan_id),
            ).fetchone()
            if plan is None or plan["status"] != "draft":
                raise PermissionError("Only draft plans are editable")
            if depends_on:
                dependency = self.db.execute(
                    """SELECT 1 FROM ago_plan_steps
                       WHERE tenant_id=%s AND plan_id=%s AND id=%s""",
                    (tenant_id, plan_id, str(UUID(depends_on))),
                ).fetchone()
                if dependency is None:
                    raise PermissionError("Dependency must be an earlier step")
            assignee = self.db.execute(
                "SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s",
                (tenant_id, assignee_id),
            ).fetchone()
            if assignee is None:
                raise PermissionError("Assignee must belong to tenant")
            position = self.db.execute(
                """SELECT COALESCE(MAX(position),0)+1 AS value
                   FROM ago_plan_steps WHERE tenant_id=%s AND plan_id=%s""",
                (tenant_id, plan_id),
            ).fetchone()["value"]
            step_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_plan_steps
                   (id,tenant_id,plan_id,position,action,assignee_id,depends_on)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (step_id, tenant_id, plan_id, position, action.strip(), assignee_id, depends_on),
            )
        return step_id

    def submit(self, *, tenant_id: str, plan_id: str, requester_id: str) -> str:
        UUID(requester_id)
        with self.db.transaction():
            plan = self.db.execute(
                """SELECT status,proposer_id FROM ago_strategy_plans
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (tenant_id, plan_id),
            ).fetchone()
            if plan is None or plan["status"] != "draft":
                raise PermissionError("Only draft plans may be submitted")
            if str(plan["proposer_id"]) != requester_id:
                raise PermissionError("Only the proposer may submit")
            steps = self.db.execute(
                """SELECT 1 FROM ago_plan_steps
                   WHERE tenant_id=%s AND plan_id=%s LIMIT 1""",
                (tenant_id, plan_id),
            ).fetchone()
            if steps is None:
                raise ValueError("A plan requires at least one step")
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=tenant_id,
                action=f"brain:activate:{plan_id}",
                requester_id=requester_id,
            )
            self.db.execute(
                """UPDATE ago_strategy_plans
                   SET status='pending_approval',approval_id=%s
                   WHERE tenant_id=%s AND id=%s""",
                (approval.request_id, tenant_id, plan_id),
            )
        return approval.request_id

    def list(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT id,goal_id,title,status,approval_id
               FROM ago_strategy_plans WHERE tenant_id=%s ORDER BY created_at,id""",
                (tenant_id,),
            ).fetchall()
        ]

    def steps(self, *, tenant_id: str, plan_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT id,position,action,assignee_id,depends_on,task_id
               FROM ago_plan_steps WHERE tenant_id=%s AND plan_id=%s
               ORDER BY position""",
                (tenant_id, plan_id),
            ).fetchall()
        ]
