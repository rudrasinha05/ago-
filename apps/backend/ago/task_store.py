"""Durable governed tasks; authorization and transition are atomic under row lock."""
from __future__ import annotations

from uuid import UUID

from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.workflows import GovernedTask, TaskStatus


class TaskStore:
    def __init__(self, connection):
        self.connection = connection

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
                task is None or approval is None or task["status"] != "proposed"
                or approval["status"] != "pending" or task["action"] != approval["action"]
            ):
                raise PermissionError("Matching pending approval required")
            self.connection.execute(
                """UPDATE ago_governed_tasks
                   SET status='waiting_approval', approval_id=%s, updated_at=now()
                   WHERE id=%s AND tenant_id=%s""",
                (approval_id, task_id, tenant_id),
            )

    def authorize_and_start(
        self, *, task_id: str, principal: Principal,
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
            if not SecurityControls(self.connection).permitted(
                principal, "task:execute", tenant_id
            ):
                raise PermissionError("Execution permission required")
            approval = self.connection.execute(
                """SELECT status, action FROM ago_approval_requests
                   WHERE id=%s AND tenant_id=%s FOR UPDATE""",
                (task["approval_id"], tenant_id),
            ).fetchone()
            if approval is None or approval["status"] != "approved" or approval["action"] != task["action"]:
                raise PermissionError("Approved matching action required")
            self.connection.execute(
                """UPDATE ago_governed_tasks
                   SET status='running', updated_at=now()
                   WHERE id=%s AND tenant_id=%s AND status='waiting_approval'""",
                (task_id, tenant_id),
            )
        return GovernedTask(
            str(task["id"]), tenant_id, task["action"], str(task["assignee_id"]),
            TaskStatus.RUNNING, str(task["approval_id"]),
        )

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
