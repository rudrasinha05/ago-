"""M3 Company Brain: tenant-scoped strategic goal hierarchy."""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope


class GoalStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def create(
        self,
        *,
        tenant_id: str,
        created_by: str,
        title: str,
        description: str = "",
        parent_id: str | None = None,
    ) -> str:
        UUID(tenant_id)
        UUID(created_by)
        if not title.strip() or len(title) > 250:
            raise ValueError("Invalid goal title")
        with self.db.transaction():
            if parent_id:
                parent = self.db.execute(
                    "SELECT status FROM ago_goals WHERE tenant_id=%s AND id=%s FOR UPDATE",
                    (tenant_id, str(UUID(parent_id))),
                ).fetchone()
                if parent is None or parent["status"] != "active":
                    raise PermissionError("Active same-tenant parent required")
            goal_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_goals(id,tenant_id,parent_id,created_by,title,description)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (goal_id, tenant_id, parent_id, created_by, title.strip(), description),
            )
        return goal_id

    def close(self, *, tenant_id: str, goal_id: str, status: str) -> None:
        if status not in ("completed", "cancelled"):
            raise ValueError("Invalid terminal status")
        with self.db.transaction():
            current = self.db.execute(
                "SELECT status FROM ago_goals WHERE tenant_id=%s AND id=%s FOR UPDATE",
                (tenant_id, goal_id),
            ).fetchone()
            if current is None or current["status"] != "active":
                raise ValueError("Goal is not active")
            child = self.db.execute(
                """SELECT 1 FROM ago_goals WHERE tenant_id=%s
                   AND parent_id=%s AND status='active'""",
                (tenant_id, goal_id),
            ).fetchone()
            if child:
                raise PermissionError("Close active child goals first")
            self.db.execute(
                "UPDATE ago_goals SET status=%s WHERE tenant_id=%s AND id=%s",
                (status, tenant_id, goal_id),
            )

    def list(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT id,parent_id,title,description,status FROM ago_goals
               WHERE tenant_id=%s ORDER BY created_at,id""",
                (tenant_id,),
            ).fetchall()
        ]
