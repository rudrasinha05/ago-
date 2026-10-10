"""Explicit operator-only M6 RBAC upgrade for pre-existing AGO tenants.

No migration silently grants a new permission to an existing user.
"""
from __future__ import annotations

import argparse
import os
from uuid import UUID

from ago.security_controls import SecurityControls

ROLE_PERMISSIONS = {
    "founder": (
        "operations:request", "operations:respond", "operations:read",
        "calendar:write", "calendar:read", "calendar:respond",
        "knowledge:write", "knowledge:read", "knowledge:review",
        "council:propose", "council:vote", "council:read", "council:finalize",
    ),
    "reviewer": (
        "operations:respond", "operations:read",
        "calendar:read", "calendar:respond",
        "knowledge:read", "knowledge:review",
        "council:vote", "council:read",
    ),
}


def grant_existing_role(db, *, tenant_id: str, role: str,
                        confirmed: bool = False) -> int:
    UUID(tenant_id)
    if role not in ROLE_PERMISSIONS:
        raise ValueError("Role not in M6 operator allowlist")
    if not confirmed:
        raise PermissionError("Explicit operator approval is required")
    with db.transaction():
        active = db.execute(
            """SELECT 1 FROM ago_user_roles WHERE tenant_id=%s AND role=%s
               LIMIT 1""",
            (tenant_id, role),
        ).fetchone()
        if active is None:
            raise LookupError("No matching role assignment for this tenant")
        controls = SecurityControls(db)
        for permission in ROLE_PERMISSIONS[role]:
            controls.grant(tenant_id, role, permission)
    return len(ROLE_PERMISSIONS[role])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grant M6 permissions to a reviewed pre-existing tenant role",
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--role", choices=sorted(ROLE_PERMISSIONS), required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Supply --confirm only after reviewing the role's permissions")
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        parser.error("AGO_POSTGRES_DSN must be configured")
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        total = grant_existing_role(
            db, tenant_id=args.tenant_id, role=args.role, confirmed=True,
        )
    print(f"Granted {total} M6 permissions to reviewed role {args.role}")


if __name__ == "__main__":
    main()
