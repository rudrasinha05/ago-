"""M9 authenticated self-profile and navigation capabilities.

Only current actor's information; no privilege mutation or cross-tenant lookup.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials

from ago.api_m2 import allowed, authenticated, bearer, db_connection, translate_error
from ago.security_controls import SecurityControls
from ago.governance import ApprovalRepository
from ago.task_store import TaskStore
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


@router.post("/logout")
def logout(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer)
    ] = None,
):
    """Revoke the exact current bearer, then let the browser discard its copy."""
    if credentials is not None:
        SecurityControls(db).revoke_session(
            credentials.credentials, actor.tenant_id,
            datetime.now(timezone.utc) + timedelta(days=1),
        )
    return {"status": "revoked"}


@router.post("/tasks/{task_id}/request-approval")
def request_task_approval(
    task_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    """Atomically propose the exact task action and attach its M2 approval."""
    allowed(db, actor, "task:create")
    allowed(db, actor, "approval:request")
    try:
        with db.transaction():
            task = db.execute(
                """SELECT action,status FROM ago_governed_tasks
                   WHERE id=%s AND tenant_id=%s FOR UPDATE""",
                (str(task_id), actor.tenant_id),
            ).fetchone()
            if task is None:
                raise LookupError("Task not found")
            if task["status"] != "proposed":
                raise PermissionError("Only unsubmitted tasks can request approval")
            proposal = ApprovalRepository(db).propose(
                tenant_id=actor.tenant_id, requester_id=actor.subject,
                action=task["action"],
            )
            TaskStore(db).request_approval(
                task_id=str(task_id), tenant_id=actor.tenant_id,
                approval_id=proposal.request_id,
            )
        return {"approval_id":proposal.request_id,"status":"waiting_approval"}
    except (ValueError, LookupError, PermissionError) as exc:
        translate_error(exc)


@router.get("/task-reviews")
def task_reviews(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "qa:read")
    return [dict(row) for row in db.execute(
        """SELECT task_id,reviewer_id,verdict,created_at
           FROM ago_task_reviews WHERE tenant_id=%s
           ORDER BY created_at DESC,task_id LIMIT 100""",
        (actor.tenant_id,),
    ).fetchall()]
