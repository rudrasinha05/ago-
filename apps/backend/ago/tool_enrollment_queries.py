"""Context-owned infrastructure queries; caller controls transaction lifetime."""

from typing import Any

from ago.backend_contracts import Cursor, DatabaseConnection, RepositoryScope


class ToolEnrollmentQueries:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def insert_ago_tool_enrollment_audit_01(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_tool_enrollment_audit\n               (tenant_id,enrollment_id,actor_id,event,rationale)\n               VALUES (%s,%s,%s,%s,%s)",
            parameters,
        )

    def select_ago_tenants_02(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", parameters
        )

    def select_ago_tool_enrollments_03(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,status FROM ago_tool_enrollments\n                   WHERE tenant_id=%s AND tool_code=%s\n                     AND status IN ('proposed','active')",
            parameters,
        )

    def insert_ago_tool_enrollments_04(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "INSERT INTO ago_tool_enrollments\n                   (id,tenant_id,tool_code,proposer_id,approval_id)\n                   VALUES (%s,%s,%s,%s,%s)",
            parameters,
        )

    def select_ago_tool_enrollments_05(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status,approval_id,tool_code FROM ago_tool_enrollments\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def select_ago_approval_requests_06(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status,action FROM ago_approval_requests\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def update_ago_tool_enrollments_07(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_tool_enrollments\n                   SET status=%s,changed_at=now()\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def select_ago_tool_enrollments_08(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT 1 FROM ago_tool_enrollments\n               WHERE tenant_id=%s AND tool_code=%s AND status='active'",
            parameters,
        )

    def select_ago_tool_enrollments_09(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT status FROM ago_tool_enrollments\n                   WHERE tenant_id=%s AND id=%s FOR UPDATE",
            parameters,
        )

    def update_ago_tool_enrollments_10(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "UPDATE ago_tool_enrollments SET status='disabled',changed_at=now()\n                   WHERE tenant_id=%s AND id=%s",
            parameters,
        )

    def select_ago_tool_enrollments_11(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT id,tool_code,proposer_id,approval_id,status,created_at,changed_at\n               FROM ago_tool_enrollments WHERE tenant_id=%s\n               ORDER BY created_at DESC,id LIMIT 200",
            parameters,
        )

    def select_ago_tool_enrollment_audit_12(self, parameters: Any = None) -> Cursor:
        return self.connection.execute(
            "SELECT actor_id,event,rationale,created_at\n               FROM ago_tool_enrollment_audit\n               WHERE tenant_id=%s AND enrollment_id=%s\n               ORDER BY id LIMIT 200",
            parameters,
        )
