"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class MetaBrainQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_executive_snapshots_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,digest,metrics,risk_flags FROM ago_executive_snapshots\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_meta_recommendations_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id FROM ago_meta_recommendations\n                       WHERE tenant_id=%s AND snapshot_id=%s AND category=%s",
            parameters,
        )

    def insert_ago_meta_recommendations_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_meta_recommendations\n                       (id,tenant_id,snapshot_id,proposer_id,category,\n                        summary,evidence,approval_id)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            parameters,
        )

    def select_ago_meta_recommendations_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status,approval_id FROM ago_meta_recommendations\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_approval_requests_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status,action FROM ago_approval_requests\n                   WHERE tenant_id=%s AND id=%s FOR SHARE",
            parameters,
        )

    def update_ago_meta_recommendations_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_meta_recommendations SET status=%s,decided_at=now()\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def select_ago_meta_recommendations_07(self, parameters: Any = None, *, extra: str) -> Cursor:
        if extra not in ("", " AND snapshot_id=%s"):
            raise ValueError("Unapproved static query selector")
        return self.connection.execute(
            "SELECT id,snapshot_id,proposer_id,category,summary,evidence,\n                      approval_id,status,decided_at,created_at\n               FROM ago_meta_recommendations WHERE tenant_id=%s"
            + extra
            + " ORDER BY recommendation_order LIMIT %s",
            parameters,
        )
