"""Operator-only independent human reviewer provisioning.

Usage: python -m ago.provision --tenant-id UUID --email reviewer@example.test
Requires AGO_POSTGRES_DSN. Password entered through getpass.
"""
from __future__ import annotations

import argparse
import getpass
import os
from uuid import UUID

from ago.identity import IdentityRepository
from ago.security_controls import SecurityControls


def add_reviewer(connection, *, tenant_id: str, email: str, password: str) -> str:
    tenant_id = str(UUID(tenant_id))
    with connection.transaction():
        department = connection.execute(
            """SELECT id FROM ago_departments
               WHERE tenant_id=%s ORDER BY name, id LIMIT 1""",
            (tenant_id,),
        ).fetchone()
        if department is None:
            raise ValueError("Tenant has no department; bootstrap first")
        reviewer = IdentityRepository(connection).create_user(
            tenant_id, email, password
        )
        connection.execute(
            """INSERT INTO ago_employees
               (id, tenant_id, department_id, name, kind)
               VALUES (%s, %s, %s, %s, 'human')""",
            (
                reviewer.user_id, tenant_id, department["id"],
                reviewer.email,
            ),
        )
        IdentityRepository(connection).assign_role(
            tenant_id, reviewer.user_id, "reviewer",
        )
        security = SecurityControls(connection)
        for permission in (
            "approval:decide", "approval:read", "qa:review", "qa:read",
            "memory:read", "operations:respond", "operations:read",
            "calendar:read", "calendar:respond",
            "knowledge:review", "knowledge:read",
            "council:vote", "council:read",
        ):
            security.grant(tenant_id, "reviewer", permission)
        return reviewer.user_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision independent AGO reviewer")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        parser.error("AGO_POSTGRES_DSN is required")
    password = getpass.getpass("Reviewer password (>=12 characters): ")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as db:
        user_id = add_reviewer(
            db, tenant_id=args.tenant_id, email=args.email,
            password=password,
        )
    print(f"Independent reviewer created: {user_id}")


if __name__ == "__main__":
    main()
