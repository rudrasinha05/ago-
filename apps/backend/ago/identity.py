"""Tenant-scoped PostgreSQL identity persistence. No public login endpoints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from ago.security import Principal, hash_password, verify_password


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    tenant_id: str
    email: str
    active: bool


class IdentityRepository:
    def __init__(self, connection: Any):
        self.connection = connection

    def create_tenant(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Tenant name required")
        tenant_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO ago_tenants(id, name) VALUES (%s, %s)",
            (tenant_id, name),
        )
        return tenant_id

    def create_user(self, tenant_id: str, email: str, password: str) -> UserRecord:
        normalized = email.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("Valid email required")
        user_id = str(uuid4())
        self.connection.execute(
            """INSERT INTO ago_users(id, tenant_id, email, password_hash)
               VALUES (%s, %s, %s, %s)""",
            (user_id, tenant_id, normalized, hash_password(password)),
        )
        return UserRecord(user_id, tenant_id, normalized, True)

    def assign_role(self, tenant_id: str, user_id: str, role: str) -> None:
        if not role:
            raise ValueError("Role required")
        self.connection.execute(
            """INSERT INTO ago_user_roles(tenant_id, user_id, role)
               SELECT tenant_id, id, %s FROM ago_users
               WHERE id=%s AND tenant_id=%s
               ON CONFLICT DO NOTHING""",
            (role, user_id, tenant_id),
        )

    def authenticate(self, tenant_id: str, email: str, password: str) -> Principal | None:
        row = self.connection.execute(
            """SELECT id, password_hash FROM ago_users
               WHERE tenant_id=%s AND email=%s AND active=true""",
            (tenant_id, email.strip().lower()),
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        roles = self.connection.execute(
            """SELECT role FROM ago_user_roles
               WHERE tenant_id=%s AND user_id=%s ORDER BY role""",
            (tenant_id, row["id"]),
        ).fetchall()
        return Principal(str(row["id"]), tenant_id, tuple(item["role"] for item in roles))

    def deactivate_user(self, tenant_id: str, user_id: str) -> bool:
        row = self.connection.execute(
            """UPDATE ago_users SET active=false
               WHERE tenant_id=%s AND id=%s AND active=true RETURNING id""",
            (tenant_id, user_id),
        ).fetchone()
        return row is not None
