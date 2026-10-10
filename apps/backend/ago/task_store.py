"""Durable governed tasks; authorization and transition are atomic under row lock."""

from __future__ import annotations

from uuid import UUID

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.workflows import GovernedTask, TaskStatus


class TaskStore:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def propose(self, *, tenant_id: str, action: str, assignee_id: str) -> GovernedTask:
        task = GovernedTask.propose(tenant_id, action, assignee_id)
        for identifier in (tenant_id, assignee_id):
            UUID(identifier)
        with self.connection.transaction():
            self.connection.execute(
                """INSERT INTO ago_governed_tasks
                   (id, tenant_id, action, assignee_id, status)
                   VALUES (%s, %s, %s, %s, %s)""",
                (task.id, tenant_id, action, assignee_id, task.status.value),
            )
        return task

    def request_approval(self, *, task_id: str, tenant_id: str, approval_id: str) -> None:
        with self.connection.transaction():
            task = self.connection.execute(
                """SELECT action, status FROM ago_governed_tasks
                   WHERE id=%s AND tenant_id=%s FOR UPDATE""",
                (task_id, tenant_id),
            ).fetchone()
            approval = self.connection.execute(
                """SELECT action, status FROM ago_approval_requests
                   WHERE id=%s AND tenant_id=%s""",
                (approval_id, tenant_id),
            ).fetchone()
            if (
                task is None
                or approval is None
                or task["status"] != "proposed"
                or approval["status"] != "pending"
                or task["action"] != approval["action"]
            ):
                raise PermissionError("Matching pending approval required")
            self.connection.execute(
                """UPDATE ago_governed_tasks
                   SET status='waiting_approval', approval_id=%s, updated_at=now()
                   WHERE id=%s AND tenant_id=%s""",
                (approval_id, task_id, tenant_id),
            )

    def authorize_and_start(
        self,
        *,
        task_id: str,
        principal: Principal,
    ) -> GovernedTask:
        tenant_id = principal.tenant_id
        with self.connection.transaction():
            task = self.connection.execute(
                """SELECT id, tenant_id, action, assignee_id, status, approval_id
                   FROM ago_governed_tasks WHERE id=%s AND tenant_id=%s FOR UPDATE""",
                (task_id, tenant_id),
            ).fetchone()
            if task is None or task["status"] != "waiting_approval" or not task["approval_id"]:
                raise PermissionError("Task awaiting valid approval required")
            if not self.repositories.resolve(SecurityControls).permitted(
                principal, "task:execute", tenant_id
            ):
                raise PermissionError("Execution permission required")
            approval = self.connection.execute(
                """SELECT status, action FROM ago_approval_requests
                   WHERE id=%s AND tenant_id=%s FOR UPDATE""",
                (task["approval_id"], tenant_id),
            ).fetchone()
            if (
                approval is None
                or approval["status"] != "approved"
                or approval["action"] != task["action"]
            ):
                raise PermissionError("Approved matching action required")
            # M3 plan tasks must respect active strategy and reviewed prerequisites.
            blocked_plan = self.connection.execute(
                """SELECT 1 FROM ago_plan_steps s
                   JOIN ago_strategy_plans p ON p.tenant_id=s.tenant_id
                     AND p.id=s.plan_id
                   JOIN ago_goals g ON g.tenant_id=p.tenant_id
                     AND g.id=p.goal_id
                   WHERE s.tenant_id=%s AND s.task_id=%s
                     AND (p.status <> 'active' OR g.status <> 'active') LIMIT 1""",
                (tenant_id, task_id),
            ).fetchone()
            if blocked_plan:
                raise PermissionError("Parent strategy or goal is no longer active")
            blocked_dependency = self.connection.execute(
                """SELECT 1 FROM ago_plan_steps s
                   JOIN ago_plan_steps prerequisite
                     ON prerequisite.tenant_id=s.tenant_id
                    AND prerequisite.plan_id=s.plan_id
                    AND prerequisite.id=s.depends_on
                   LEFT JOIN ago_governed_tasks previous
                     ON previous.tenant_id=s.tenant_id
                    AND previous.id=prerequisite.task_id
                   LEFT JOIN ago_task_reviews review
                     ON review.tenant_id=s.tenant_id
                    AND review.task_id=prerequisite.task_id
                   WHERE s.tenant_id=%s AND s.task_id=%s
                     AND s.depends_on IS NOT NULL
                     AND (previous.status IS DISTINCT FROM 'completed'
                          OR review.verdict IS DISTINCT FROM 'pass') LIMIT 1""",
                (tenant_id, task_id),
            ).fetchone()
            if blocked_dependency:
                raise PermissionError("Predecessor requires completed task and passing QA")
            self.connection.execute(
                """UPDATE ago_governed_tasks
                   SET status='running', updated_at=now()
                   WHERE id=%s AND tenant_id=%s AND status='waiting_approval'""",
                (task_id, tenant_id),
            )
        return GovernedTask(
            str(task["id"]),
            tenant_id,
            task["action"],
            str(task["assignee_id"]),
            TaskStatus.RUNNING,
            str(task["approval_id"]),
        )

    def list_tasks(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid task list limit")
        rows = self.connection.execute(
            """SELECT id, action, assignee_id, approval_id, status, created_at
               FROM ago_governed_tasks WHERE tenant_id=%s
               ORDER BY created_at DESC, id LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def finish(self, *, task_id: str, tenant_id: str, success: bool) -> None:
        with self.connection.transaction():
            row = self.connection.execute(
                """UPDATE ago_governed_tasks
                   SET status=%s, updated_at=now()
                   WHERE id=%s AND tenant_id=%s AND status='running'
                   RETURNING id""",
                ("completed" if success else "failed", task_id, tenant_id),
            ).fetchone()
            if row is None:
                raise ValueError("Only running tasks may finish")
