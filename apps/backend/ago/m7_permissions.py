"""Explicit, local-operator-only M7 role upgrade for existing AGO tenants.

Migrations never grant new powers to pre-existing roles automatically.
"""
from __future__ import annotations

import argparse
import os
from uuid import UUID

from ago.security_controls import SecurityControls


ROLE_PERMISSIONS = {
    "founder": (
        "meta:dna:propose", "meta:dna:read", "meta:dna:activate",
        "meta:observe", "meta:read", "meta:simulate",
        "meta:recommend", "meta:finalize",
    ),
    "reviewer": ("meta:dna:read", "meta:read"),
}


def grant_existing_role(
    db, *, tenant_id: str, role: str, confirmed: bool = False,
) -> int:
    tenant_id = str(UUID(tenant_id))
    if role not in ROLE_PERMISSIONS:
        raise ValueError("Only founder and reviewer roles can be upgraded")
    if not confirmed:
        raise PermissionError("Explicit local operator confirmation required")
    with db.transaction():
        assigned = db.execute(
            """SELECT 1 FROM ago_user_roles
               WHERE tenant_id=%s AND role=%s LIMIT 1""",
            (tenant_id, role),
        ).fetchone()
        if assigned is None:
            raise LookupError("Tenant does not have the specified role")
        controls = SecurityControls(db)
        for permission in ROLE_PERMISSIONS[role]:
            controls.grant(tenant_id, role, permission)
    return len(ROLE_PERMISSIONS[role])


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually grant M7 scoped permissions")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--role", choices=sorted(ROLE_PERMISSIONS), required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Review the role's permissions, then supply --confirm")
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        parser.error("AGO_POSTGRES_DSN must be set")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as db:
        count = grant_existing_role(
            db, tenant_id=args.tenant_id, role=args.role, confirmed=True,
        )
    print(f"Granted {count} M7 permissions to {args.role} role")


if __name__ == "__main__":
    main()
