"""PostgreSQL-backed authorization grants, session revocation, and audit records."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.security import Principal


class SecurityControls:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def grant(self, tenant_id: str, role: str, permission: str) -> None:
        if not tenant_id or not role or not permission:
            raise ValueError("Tenant, role and permission required")
        self.connection.execute(
            """INSERT INTO ago_role_permissions(tenant_id, role, permission)
               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
            (tenant_id, role, permission),
        )

    def revoke_grant(self, tenant_id: str, role: str, permission: str) -> None:
        self.connection.execute(
            """DELETE FROM ago_role_permissions
               WHERE tenant_id=%s AND role=%s AND permission=%s""",
            (tenant_id, role, permission),
        )

    def permitted(self, principal: Principal, permission: str, tenant_id: str) -> bool:
        if not permission or principal.tenant_id != tenant_id:
            return False
        row = self.connection.execute(
            """SELECT 1 FROM ago_users u
               JOIN ago_user_roles r ON r.user_id=u.id AND r.tenant_id=u.tenant_id
               JOIN ago_role_permissions p ON p.role=r.role AND p.tenant_id=r.tenant_id
               WHERE u.id=%s AND u.tenant_id=%s AND u.active=true
                 AND p.permission=%s LIMIT 1""",
            (principal.subject, tenant_id, permission),
        ).fetchone()
        return row is not None

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def revoke_session(self, token: str, tenant_id: str, expires_at: Any) -> None:
        self.connection.execute(
            """INSERT INTO ago_revoked_sessions(token_hash, tenant_id, expires_at)
               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
            (self.token_hash(token), tenant_id, expires_at),
        )

    def is_revoked(self, token: str) -> bool:
        return (
            self.connection.execute(
                """SELECT 1 FROM ago_revoked_sessions
               WHERE token_hash=%s AND expires_at>now()""",
                (self.token_hash(token),),
            ).fetchone()
            is not None
        )

    def audit(
        self,
        action: str,
        outcome: str,
        *,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not action or not outcome:
            raise ValueError("Audit action and outcome required")
        self.connection.execute(
            """INSERT INTO ago_security_audit
               (tenant_id, actor_id, action, outcome, metadata)
               VALUES (%s, %s, %s, %s, %s::jsonb)""",
            (tenant_id, actor_id, action, outcome, json.dumps(metadata or {})),
        )
