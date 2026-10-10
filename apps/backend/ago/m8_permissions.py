"""Explicit offline operator-only role upgrade for M8 existing tenants.

Migrations NEVER silently expand any person's privileges.
"""
from __future__ import annotations

import argparse
import os
from uuid import UUID

from ago.security_controls import SecurityControls

ROLE_PERMISSIONS = {
    "founder": (
        "tool:enroll", "tool:read", "tool:dispatch", "tool:recover",
        "automation:manage", "automation:read", "automation:run",
    ),
    "reviewer": ("tool:read", "automation:read"),
}


def grant_existing_role(
    db, *, tenant_id: str, role: str, confirmed: bool = False,
) -> int:
    tenant_id = str(UUID(tenant_id))
    if role not in ROLE_PERMISSIONS:
        raise ValueError("Only reviewed founder/reviewer roles can be upgraded")
    if not confirmed:
        raise PermissionError("Explicit operator permission review required")
    with db.transaction():
        match = db.execute(
            """SELECT 1 FROM ago_user_roles WHERE tenant_id=%s AND role=%s
               LIMIT 1""",
            (tenant_id, role),
        ).fetchone()
        if match is None:
            raise LookupError("Role has no assignments in this tenant")
        controls = SecurityControls(db)
        for permission in ROLE_PERMISSIONS[role]:
            controls.grant(tenant_id, role, permission)
    return len(ROLE_PERMISSIONS[role])


def main():
    parser = argparse.ArgumentParser(description="Explicit M8 tenant role upgrade")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--role", choices=sorted(ROLE_PERMISSIONS), required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Review M8 role allowlist and supply --confirm")
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        parser.error("AGO_POSTGRES_DSN required")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as db:
        count = grant_existing_role(
            db, tenant_id=args.tenant_id, role=args.role, confirmed=True,
        )
    print(f"M8 granted {count} role permissions for {args.role}")


if __name__ == "__main__":
    main()
