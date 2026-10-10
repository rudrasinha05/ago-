"""M9 authenticated self-profile and navigation capabilities.

Only current actor's information; no privilege mutation or cross-tenant lookup.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials

from ago.api_m2 import (
    allowed,
    authenticated,
    bearer,
    db_connection,
    repository_scope,
    translate_error,
)
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import ConsoleServicePort, ConsoleStorePort, SecurityControlsPort
from ago.security import Principal

router = APIRouter(prefix="/v1/console", tags=["M9 Control Center"])


@router.get("/me")
def me(
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    return repositories.resolve(ConsoleStorePort).me(actor)


@router.post("/logout")
def logout(
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)] = None,
    repositories: RepositoryScope = Depends(repository_scope),
):
    """Revoke the exact current bearer, then let the browser discard its copy."""
    if credentials is not None:
        repositories.resolve(SecurityControlsPort).revoke_session(
            credentials.credentials,
            actor.tenant_id,
            datetime.now(timezone.utc) + timedelta(days=1),
        )
    return {"status": "revoked"}


@router.post("/tasks/{task_id}/request-approval")
def request_task_approval(
    task_id: UUID,
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "task:create")
    allowed(repositories, actor, "approval:request")
    try:
        return repositories.resolve(ConsoleServicePort).request_approval(str(task_id), actor)
    except (ValueError, LookupError, PermissionError) as exc:
        translate_error(exc)


@router.get("/task-reviews")
def task_reviews(
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "qa:read")
    return repositories.resolve(ConsoleStorePort).task_reviews(actor)


@router.get("/qa-queue")
def pending_qa(
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "qa:read")
    return repositories.resolve(ConsoleStorePort).pending_qa(actor)
