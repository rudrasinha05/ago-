"""M9 authenticated self-profile and navigation capabilities.

Only current actor's information; no privilege mutation or cross-tenant lookup.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ago.api_m2 import authenticated, db_connection
from ago.security import Principal

router = APIRouter(prefix="/v1/console", tags=["M9 Control Center"])


@router.get("/me")
def me(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    row = db.execute(
        """SELECT u.email,e.name FROM ago_users u
           LEFT JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
           WHERE u.tenant_id=%s AND u.id=%s AND u.active=true""",
        (actor.tenant_id, actor.subject),
    ).fetchone()
    roles = db.execute(
        """SELECT role FROM ago_user_roles
           WHERE tenant_id=%s AND user_id=%s ORDER BY role""",
        (actor.tenant_id, actor.subject),
    ).fetchall()
    permissions = db.execute(
        """SELECT DISTINCT p.permission FROM ago_user_roles r
           JOIN ago_role_permissions p ON p.tenant_id=r.tenant_id
              AND p.role=r.role
           WHERE r.tenant_id=%s AND r.user_id=%s
           ORDER BY p.permission""",
        (actor.tenant_id, actor.subject),
    ).fetchall()
    return {
        "id": actor.subject,
        "tenant_id": actor.tenant_id,
        "email": row["email"] if row else None,
        "display_name": (row["name"] if row else None) or "AGO member",
        "roles": [record["role"] for record in roles],
        "permissions": [record["permission"] for record in permissions],
    }
