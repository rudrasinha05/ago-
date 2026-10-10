"""Tenant-scoped console persistence; permissions remain enforced by adapters."""

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.security import Principal


class ConsoleStore:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def me(self, actor: Principal) -> dict:
        row = self.connection.execute(
            """SELECT u.email,e.name FROM ago_users u
               LEFT JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
               WHERE u.tenant_id=%s AND u.id=%s AND u.active=true""",
            (actor.tenant_id, actor.subject),
        ).fetchone()
        roles = self.connection.execute(
            """SELECT role FROM ago_user_roles
               WHERE tenant_id=%s AND user_id=%s ORDER BY role""",
            (actor.tenant_id, actor.subject),
        ).fetchall()
        permissions = self.connection.execute(
            """SELECT DISTINCT p.permission FROM ago_user_roles r
               JOIN ago_role_permissions p ON p.tenant_id=r.tenant_id
                  AND p.role=r.role
               WHERE r.tenant_id=%s AND r.user_id=%s
               ORDER BY p.permission""",
            (actor.tenant_id, actor.subject),
        ).fetchall()
        return {
            "id": actor.subject,
            "tenant_id": actor.tenant_id,
            "email": row["email"] if row else None,
            "display_name": (row["name"] if row else None) or "AGO member",
            "roles": [record["role"] for record in roles],
            "permissions": [record["permission"] for record in permissions],
        }

    def task_reviews(self, actor: Principal) -> list[dict]:
        return [
            dict(row)
            for row in self.connection.execute(
                """SELECT task_id,reviewer_id,verdict,created_at
               FROM ago_task_reviews WHERE tenant_id=%s
               ORDER BY created_at DESC,task_id LIMIT 100""",
                (actor.tenant_id,),
            ).fetchall()
        ]

    def pending_qa(self, actor: Principal) -> list[dict]:
        """Minimal unreviewed completed-task metadata for independent QA staff.

        QA reviewers do not receive a broad task:read permission.
        """
        return [
            dict(row)
            for row in self.connection.execute(
                """SELECT t.id,t.action,t.status,t.assignee_id,t.approval_id
               FROM ago_governed_tasks t
               WHERE t.tenant_id=%s AND t.status='completed'
                 AND NOT EXISTS (
                   SELECT 1 FROM ago_task_reviews r
                   WHERE r.tenant_id=t.tenant_id AND r.task_id=t.id
                 )
               ORDER BY t.created_at DESC,t.id LIMIT 100""",
                (actor.tenant_id,),
            ).fetchall()
        ]

    def lock_proposed_task(self, task_id: str, tenant_id: str) -> dict:
        row = self.connection.execute(
            "SELECT action,status FROM ago_governed_tasks WHERE id=%s AND tenant_id=%s FOR UPDATE",
            (task_id, tenant_id),
        ).fetchone()
        if row is None:
            raise LookupError("Task not found")
        if row["status"] != "proposed":
            raise PermissionError("Only unsubmitted tasks can request approval")
        return dict(row)

    def review(self, task_id: str, tenant_id: str) -> dict:
        row = self.connection.execute(
            """SELECT task_id, author_id, reviewer_id, verdict, evidence, created_at
               FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s""",
            (tenant_id, task_id),
        ).fetchone()
        if row is None:
            raise LookupError("Review not found")
        return dict(row)
