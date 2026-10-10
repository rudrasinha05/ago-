"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class ToolCatalogQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def select_ago_knowledge_nodes_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT count(*) FILTER (WHERE status='verified') AS verified,\n                      count(*) FILTER (WHERE status='pending') AS pending\n               FROM ago_knowledge_nodes WHERE tenant_id=%s",
            parameters,
        )
