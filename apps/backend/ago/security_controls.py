"""PostgreSQL-backed authorization grants, session revocation, and audit records."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ago.audit_redaction import audit_metadata_safe
from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance_domain import CONSTITUTION_CONTEXTS
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
        if permission == "approval:founder":
            founder = self.connection.execute(
                """SELECT 1 FROM ago_users u
                   JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
                   JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
                   WHERE u.id=%s AND u.tenant_id=%s AND u.active
                     AND e.kind='human' AND r.role='founder' LIMIT 1""",
                (principal.subject, tenant_id),
            ).fetchone()
            return founder is not None
        row = self.connection.execute(
            """SELECT 1 FROM ago_users u
               JOIN ago_user_roles r ON r.user_id=u.id AND r.tenant_id=u.tenant_id
               JOIN ago_role_permissions p ON p.role=r.role AND p.tenant_id=r.tenant_id
               WHERE u.id=%s AND u.tenant_id=%s AND u.active=true
                 AND p.permission=%s LIMIT 1""",
            (principal.subject, tenant_id, permission),
        ).fetchone()
        if row is None:
            return False
        if permission.endswith(":read") or permission in ("approval:decide", "qa:review"):
            return True
        area = permission.split(":", 1)[0]
        context = {"agent": "agents", "task": "tasks", "tool": "tools",
                   "automation": "tools", "economy": "insights", "simulation": "insights",
                   "experiments": "insights"}.get(area, area)
        return self.constitution_allowed(principal, context) if context in CONSTITUTION_CONTEXTS else True

    def constitution_allowed(self, principal: Principal, context: str) -> bool:
        """Shared execution boundary: no DNA, role, approval or emergency overrides it."""
        if context not in CONSTITUTION_CONTEXTS:
            raise ValueError("Unknown constitutional operation context")
        blocked = self.connection.execute(
            """SELECT 'constitution' AS source,revision::text AS record_id FROM
                 (SELECT revision,blocked_contexts FROM ago_constitution_adoptions
                  WHERE tenant_id=%s AND effective_at<=clock_timestamp()
                  ORDER BY revision DESC LIMIT 1) active
               WHERE %s=ANY(active.blocked_contexts)
               UNION ALL
               SELECT 'emergency' AS source,e.id::text AS record_id FROM ago_constitution_emergencies e
               WHERE e.tenant_id=%s AND e.expires_at>clock_timestamp() AND %s=ANY(e.blocked_contexts)
                 AND NOT EXISTS(SELECT 1 FROM ago_constitution_emergency_closures c
                   WHERE c.tenant_id=e.tenant_id AND c.emergency_id=e.id)
               LIMIT 1""",
            (principal.tenant_id,context,principal.tenant_id,context),
        ).fetchone()
        if blocked:
            self.audit("constitution:denied", "blocked", tenant_id=principal.tenant_id,
                       actor_id=principal.subject, metadata={"context":context, **dict(blocked)})
            return False
        return True

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
            (tenant_id, actor_id, action, outcome, json.dumps(audit_metadata_safe(metadata))),
        )
