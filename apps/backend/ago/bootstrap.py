"""Operator-only AGO bootstrap for a fresh migrated database.

Runs locally via python -m ago.bootstrap. Not exposed over HTTP.
Never commit or print the password; prompts securely when absent.
"""
from __future__ import annotations

import argparse
import getpass
import os

from ago.identity import IdentityRepository
from ago.organization_store import OrganizationStore
from ago.security_controls import SecurityControls


FOUNDER_PERMISSIONS = (
    "economy:manage",
    "economy:consume",
    "insights:read",
    "simulation:run",
    "experiments:propose",
    "experiments:read",
    "agent:dispatch",
    "agent:read",
    "brain:manage",
    "brain:read",
    "brain:activate",
    "organization:manage",
    "organization:read",
    "approval:read",
    "task:read",
    "qa:read",
    "approval:request",
    "approval:decide",
    "task:create",
    "task:execute",
    "qa:review",
    "memory:read",
    "memory:write",
)


def bootstrap(
    connection, *, organization: str, email: str, password: str,
) -> tuple[str, str]:
    """Atomic creation of first tenant, founder identity and human employee."""
    with connection.transaction():
        identities = IdentityRepository(connection)
        tenant_id = identities.create_tenant(organization)
        founder = identities.create_user(tenant_id, email, password)
        department = OrganizationStore(connection).add_department(
            tenant_id=tenant_id, name="Executive",
        )
        # Human employee identity must match authenticated user id for review rules.
        connection.execute(
            """INSERT INTO ago_employees
               (id, tenant_id, department_id, name, kind)
               VALUES (%s, %s, %s, %s, 'human')""",
            (founder.user_id, tenant_id, department.id, "Founder"),
        )
        identities.assign_role(tenant_id, founder.user_id, "founder")
        controls = SecurityControls(connection)
        for permission in FOUNDER_PERMISSIONS:
            controls.grant(tenant_id, "founder", permission)
        return tenant_id, founder.user_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a fresh AGO tenant")
    parser.add_argument("--organization", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        parser.error("AGO_POSTGRES_DSN is required")
    password = getpass.getpass("Initial founder password (>=12 characters): ")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        tenant_id, user_id = bootstrap(
            connection, organization=args.organization,
            email=args.email, password=password,
        )
    print(f"Tenant created: {tenant_id}")
    print(f"Founder created: {user_id}")
    print("Grant an independent second human the appropriate reviewer role.")


if __name__ == "__main__":
    main()
