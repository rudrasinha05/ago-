"""Authenticated M2 organizational API.

All mutations take identity from signed, nonrevoked sessions and check persistent
tenant-scoped database grants. No caller-provided 'authorized' field is accepted.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, StrictBool

from ago.api_contracts import StrictInput
from ago.backend_contracts import RepositoryScope
from ago.governed_execution import GovernanceGate
from ago.memory import MemoryRecord
from ago.quality import Verdict
from ago.repository_ports import (
    REPOSITORY_BINDINGS,
    ApprovalRepositoryPort,
    ConsoleStorePort,
    IdentityRepositoryPort,
    MemoryStorePort,
    OrganizationStorePort,
    QualityStorePort,
    SecurityControlsPort,
    SessionServicePort,
    TaskStorePort,
)
from ago.security import AuthenticationError, Principal, SessionTokens

router = APIRouter(prefix="/v1", tags=["M2 organization"])
bearer = HTTPBearer(auto_error=False)


class Login(StrictInput):
    tenant_id: UUID
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class DepartmentInput(StrictInput):
    name: str = Field(min_length=1, max_length=150)


class EmployeeInput(StrictInput):
    department_id: UUID
    name: str = Field(min_length=1, max_length=150)
    kind: Literal["human", "ai"]
    manager_id: UUID | None = None


class ActionInput(StrictInput):
    action: str = Field(min_length=1, max_length=500)


class TaskInput(ActionInput):
    assignee_id: UUID


class ApprovalLink(StrictInput):
    approval_id: UUID


class DecisionInput(StrictInput):
    approve: StrictBool
    reason: str = Field(min_length=1, max_length=3000)


class FinishInput(StrictInput):
    success: StrictBool


class ReviewInput(StrictInput):
    verdict: Verdict
    evidence: str = Field(min_length=1, max_length=5000)


class MemoryInput(StrictInput):
    content: str = Field(min_length=1, max_length=20_000)
    visibility: Literal["private", "tenant"] = "private"


def session_tokens() -> SessionTokens:
    secret = os.getenv("AGO_SESSION_SECRET")
    if not secret or len(secret.encode()) < 32:
        raise HTTPException(503, "Authentication not configured")
    return SessionTokens(secret)


def db_connection():
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503, "Database not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(dsn, connect_timeout=3, row_factory=dict_row, autocommit=True) as db:
            yield db
    except ImportError as exc:
        raise HTTPException(503, "PostgreSQL driver unavailable") from exc
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc


def repository_scope(request: Request, db=Depends(db_connection)) -> RepositoryScope:
    return RepositoryScope(
        db,
        bindings=REPOSITORY_BINDINGS,
        overrides=getattr(request.app.state, "repository_overrides", {}),
    )


def verified_bearer(
    credential: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)] = None,
) -> tuple[Principal, str]:
    """Reject missing/invalid HMAC bearer before opening a database connection."""
    if credential is None or credential.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        principal = session_tokens().verify(credential.credentials)
        UUID(principal.tenant_id)
        UUID(principal.subject)
        return principal, credential.credentials
    except (AuthenticationError, ValueError) as exc:
        raise HTTPException(401, "Invalid session", headers={"WWW-Authenticate": "Bearer"}) from exc


def authenticated(
    verified: Annotated[tuple[Principal, str], Depends(verified_bearer)],
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
) -> Principal:
    principal, token = verified
    try:
        security = repositories.resolve(SecurityControlsPort)
        if security.is_revoked(token):
            raise AuthenticationError("Revoked token")
        active = repositories.resolve(IdentityRepositoryPort).active(
            principal.tenant_id, principal.subject
        )
        if not active:
            raise AuthenticationError("Inactive account")
        return principal
    except (AuthenticationError, ValueError) as exc:
        raise HTTPException(401, "Invalid session", headers={"WWW-Authenticate": "Bearer"}) from exc


def allowed(repositories: RepositoryScope, principal: Principal, permission: str) -> None:
    if not repositories.resolve(SecurityControlsPort).permitted(
        principal, permission, principal.tenant_id
    ):
        raise HTTPException(403, "Permission denied")


def translate_error(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(403, str(exc)) from exc
    if isinstance(exc, LookupError):
        raise HTTPException(404, str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(400, str(exc)) from exc
    raise exc


@router.post("/sessions")
def login(
    data: Login,
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    tokens = session_tokens()
    try:
        principal = repositories.resolve(SessionServicePort).authenticate(
            str(data.tenant_id), data.email, data.password
        )
    except AuthenticationError as exc:
        raise HTTPException(401, "Invalid credentials") from exc
    return {"access_token": tokens.issue(principal), "token_type": "bearer"}


@router.post("/organization/departments")
def add_department(
    data: DepartmentInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    try:
        return asdict(
            repositories.resolve(OrganizationStorePort).add_department(
                tenant_id=actor.tenant_id, name=data.name
            )
        )
    except ValueError as exc:
        translate_error(exc)


@router.post("/organization/employees")
def add_employee(
    data: EmployeeInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    try:
        return asdict(
            repositories.resolve(OrganizationStorePort).hire(
                tenant_id=actor.tenant_id,
                department_id=str(data.department_id),
                name=data.name,
                kind=data.kind,
                manager_id=str(data.manager_id) if data.manager_id else None,
            )
        )
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/governance/approvals")
def request_approval(
    data: ActionInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "approval:request")
    try:
        return asdict(
            repositories.resolve(ApprovalRepositoryPort).propose(
                tenant_id=actor.tenant_id,
                action=data.action,
                requester_id=actor.subject,
            )
        )
    except ValueError as exc:
        translate_error(exc)


@router.post("/governance/approvals/{request_id}/decision")
def decide_approval(
    request_id: UUID,
    data: DecisionInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        decision = GovernanceGate(
            repositories.resolve(ApprovalRepositoryPort), repositories.resolve(SecurityControlsPort)
        ).decide(
            principal=actor,
            request_id=str(request_id),
            tenant_id=actor.tenant_id,
            approve=data.approve,
            reason=data.reason,
        )
        return asdict(decision)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/tasks")
def create_task(
    data: TaskInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "task:create")
    try:
        return asdict(
            repositories.resolve(TaskStorePort).propose(
                tenant_id=actor.tenant_id,
                action=data.action,
                assignee_id=str(data.assignee_id),
            )
        )
    except ValueError as exc:
        translate_error(exc)


@router.post("/tasks/{task_id}/approval")
def attach_approval(
    task_id: UUID,
    data: ApprovalLink,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "task:create")
    try:
        repositories.resolve(TaskStorePort).request_approval(
            task_id=str(task_id),
            tenant_id=actor.tenant_id,
            approval_id=str(data.approval_id),
        )
    except (PermissionError, ValueError) as exc:
        translate_error(exc)
    return {"status": "waiting_approval"}


@router.post("/tasks/{task_id}/start")
def start_task(
    task_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        task = repositories.resolve(TaskStorePort).authorize_and_start(
            task_id=str(task_id), principal=actor
        )
        return asdict(task)
    except (PermissionError, ValueError) as exc:
        translate_error(exc)


@router.post("/tasks/{task_id}/finish")
def finish_task(
    task_id: UUID,
    data: FinishInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "task:execute")
    try:
        repositories.resolve(TaskStorePort).finish(
            task_id=str(task_id),
            tenant_id=actor.tenant_id,
            success=data.success,
        )
    except ValueError as exc:
        translate_error(exc)
    return {"status": "completed" if data.success else "failed"}


@router.post("/tasks/{task_id}/review")
def review_task(
    task_id: UUID,
    data: ReviewInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        review = repositories.resolve(QualityStorePort).review(
            task_id=str(task_id),
            principal=actor,
            verdict=data.verdict,
            evidence=data.evidence,
        )
        return asdict(review)
    except (PermissionError, ValueError) as exc:
        translate_error(exc)


@router.post("/memory")
def save_memory(
    data: MemoryInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "memory:write")
    try:
        record = MemoryRecord.create(
            tenant_id=actor.tenant_id,
            owner_id=actor.subject,
            content=data.content,
            visibility=data.visibility,
        )
        repositories.resolve(MemoryStorePort).save(record)
        return {"id": record.id, "visibility": record.visibility}
    except ValueError as exc:
        translate_error(exc)


@router.get("/memory/{record_id}")
def get_memory(
    record_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "memory:read")
    try:
        record = repositories.resolve(MemoryStorePort).get(
            record_id=str(record_id),
            tenant_id=actor.tenant_id,
            reader_id=actor.subject,
        )
        return asdict(record)
    except (PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/organization/departments")
def list_departments(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:read")
    return [
        asdict(d)
        for d in repositories.resolve(OrganizationStorePort).list_departments(
            tenant_id=actor.tenant_id
        )
    ]


@router.get("/organization/employees")
def list_employees(
    department_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:read")
    return [
        asdict(e)
        for e in repositories.resolve(OrganizationStorePort).list_employees(
            tenant_id=actor.tenant_id,
            department_id=str(department_id),
        )
    ]


@router.get("/governance/approvals")
def list_approvals(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "approval:read")
    return repositories.resolve(ApprovalRepositoryPort).list_requests(tenant_id=actor.tenant_id)


@router.get("/tasks")
def list_tasks(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "task:read")
    return repositories.resolve(TaskStorePort).list_tasks(tenant_id=actor.tenant_id)


@router.get("/tasks/{task_id}/review")
def get_task_review(
    task_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "qa:read")
    return repositories.resolve(ConsoleStorePort).review(str(task_id), actor.tenant_id)
