"""M3 Company Brain: tenant-scoped strategic goal hierarchy."""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope


CONFIDENTIAL_TITLE = "Confidential founder project"


def _confidential_view(row: dict, *fields: str) -> dict:
    """Replace private founder-intake text for readers who are not its founder."""
    if row.get("founder_confidential"):
        row["title"] = CONFIDENTIAL_TITLE
        for field in fields:
            row[field] = None
    return row


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

    def list(self, *, tenant_id: str, reader_id: str | None = None) -> list[dict]:
        """List goals; a founder-intake project stays with that founder.

        Founder project intake copies the private brief into the goal
        (title = first brief line, description = whole brief; the Approval
        Inbox excerpt reads it there). Company-wide ``brain:read`` must not
        reveal either to anyone else, so for those goals both are replaced
        unless ``reader_id`` is the intake's own founder. A missing reader
        fails closed.
        """
        UUID(tenant_id)
        if reader_id is not None:
            UUID(reader_id)
        rows = self.db.execute(
            """SELECT g.id,g.parent_id,g.title,g.description,g.status,
                  EXISTS (
                    SELECT 1 FROM ago_founder_intakes i
                    WHERE i.tenant_id=g.tenant_id AND i.goal_id=g.id
                      AND i.founder_id IS DISTINCT FROM %s::uuid
                  ) AS founder_confidential
           FROM ago_goals g
           WHERE g.tenant_id=%s ORDER BY g.created_at,g.id""",
            (reader_id, tenant_id),
        ).fetchall()
        return [_confidential_view(dict(row), "description") for row in rows]
