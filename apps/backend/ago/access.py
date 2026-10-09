"""Tenant-scoped authorization service backed by persistent user-role assignments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ago.security import AuthorizationError, Principal, RolePolicy


@dataclass(frozen=True)
class AccessDecision:
    permitted: bool
    reason: str


class AccessService:
    def __init__(self, connection: Any, policy: RolePolicy):
        self.connection = connection
        self.policy = policy

    def evaluate(
        self, principal: Principal, permission: str, *,
        resource_tenant_id: str,
    ) -> AccessDecision:
        if not resource_tenant_id or principal.tenant_id != resource_tenant_id:
            return AccessDecision(False, "tenant_mismatch")
        row = self.connection.execute(
            """SELECT active FROM ago_users WHERE id=%s AND tenant_id=%s""",
            (principal.subject, principal.tenant_id),
        ).fetchone()
        if row is None or not row["active"]:
            return AccessDecision(False, "inactive_or_missing_user")
        rows = self.connection.execute(
            """SELECT role FROM ago_user_roles
               WHERE user_id=%s AND tenant_id=%s""",
            (principal.subject, principal.tenant_id),
        ).fetchall()
        # Always refresh persisted roles; never trust a potentially stale token's role list.
        current = Principal(
            principal.subject, principal.tenant_id,
            tuple(item["role"] for item in rows),
        )
        if not self.policy.allowed(current, permission, tenant_id=resource_tenant_id):
            return AccessDecision(False, "permission_denied")
        return AccessDecision(True, "allowed")

    def require(
        self, principal: Principal, permission: str, *,
        resource_tenant_id: str,
    ) -> None:
        decision = self.evaluate(
            principal, permission, resource_tenant_id=resource_tenant_id
        )
        if not decision.permitted:
            raise AuthorizationError("Access denied")
