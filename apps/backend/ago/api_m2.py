"""Authenticated M2 organizational API.

All mutations take identity from signed, nonrevoked sessions and check persistent
tenant-scoped database grants. No caller-provided 'authorized' field is accepted.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ago.governance import ApprovalRepository
from ago.governed_execution import GovernanceGate
from ago.identity import IdentityRepository
from ago.login_security import LoginThrottle
from ago.memory import MemoryRecord
from ago.organization_store import MemoryStore, OrganizationStore
from ago.quality import Verdict
from ago.quality_store import QualityStore
from ago.security import AuthenticationError, Principal, SessionTokens
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore


router = APIRouter(prefix="/v1", tags=["M2 organization"])
bearer = HTTPBearer(auto_error=False)


class Login(BaseModel):
    tenant_id: UUID
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class DepartmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class EmployeeInput(BaseModel):
    department_id: UUID
    name: str = Field(min_length=1, max_length=150)
    kind: str
    manager_id: UUID | None = None


class ActionInput(BaseModel):
    action: str = Field(min_length=1, max_length=500)


class TaskInput(ActionInput):
    assignee_id: UUID


class ApprovalLink(BaseModel):
    approval_id: UUID


class DecisionInput(BaseModel):
    approve: bool
    reason: str = Field(min_length=1, max_length=3000)


class FinishInput(BaseModel):
    success: bool


class ReviewInput(BaseModel):
    verdict: Verdict
    evidence: str = Field(min_length=1, max_length=5000)


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    visibility: str = "private"


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

        with psycopg.connect(dsn, connect_timeout=3, row_factory=dict_row) as db:
            yield db
    except ImportError as exc:
        raise HTTPException(503, "PostgreSQL driver unavailable") from exc
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc


def authenticated(
    db=Depends(db_connection),
    credential: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)] = None,
) -> Principal:
    if credential is None or credential.scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        principal = session_tokens().verify(credential.credentials)
        UUID(principal.tenant_id)
        UUID(principal.subject)
        security = SecurityControls(db)
        if security.is_revoked(credential.credentials):
            raise AuthenticationError("Revoked token")
        active = db.execute(
            "SELECT 1 FROM ago_users WHERE id=%s AND tenant_id=%s AND active=true",
            (principal.subject, principal.tenant_id),
        ).fetchone()
        if active is None:
            raise AuthenticationError("Inactive account")
        return principal
    except (AuthenticationError, ValueError) as exc:
        raise HTTPException(
            401, "Invalid session", headers={"WWW-Authenticate": "Bearer"}
        ) from exc


def allowed(db, principal: Principal, permission: str) -> None:
    if not SecurityControls(db).permitted(principal, permission, principal.tenant_id):
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
def login(data: Login, db=Depends(db_connection)):
    tokens = session_tokens()
    tenant_id = str(data.tenant_id)
    throttle = LoginThrottle(db)
    if not throttle.begin(tenant_id, data.email):
        db.commit()
        raise HTTPException(401, "Invalid credentials")
    principal = IdentityRepository(db).authenticate(
        tenant_id, data.email, data.password
    )
    if principal is None:
        throttle.failure(tenant_id, data.email)
        db.commit()  # Persist failed attempts even though HTTP returns 401.
        raise HTTPException(401, "Invalid credentials")
    throttle.success(tenant_id, data.email)
    return {"access_token": tokens.issue(principal), "token_type": "bearer"}


@router.post("/organization/departments")
def add_department(
    data: DepartmentInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "organization:manage")
    try:
        return asdict(OrganizationStore(db).add_department(
            tenant_id=actor.tenant_id, name=data.name
        ))
    except ValueError as exc:
        translate_error(exc)


@router.post("/organization/employees")
def add_employee(
    data: EmployeeInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "organization:manage")
    try:
        return asdict(OrganizationStore(db).hire(
            tenant_id=actor.tenant_id, department_id=str(data.department_id),
            name=data.name, kind=data.kind,
            manager_id=str(data.manager_id) if data.manager_id else None,
        ))
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/governance/approvals")
def request_approval(
    data: ActionInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "approval:request")
    try:
        return asdict(ApprovalRepository(db).propose(
            tenant_id=actor.tenant_id, action=data.action,
            requester_id=actor.subject,
        ))
    except ValueError as exc:
        translate_error(exc)


@router.post("/governance/approvals/{request_id}/decision")
def decide_approval(
    request_id: UUID, data: DecisionInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    try:
        decision = GovernanceGate(
            ApprovalRepository(db), SecurityControls(db)
        ).decide(
            principal=actor, request_id=str(request_id),
            tenant_id=actor.tenant_id, approve=data.approve, reason=data.reason,
        )
        return asdict(decision)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/tasks")
def create_task(
    data: TaskInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "task:create")
    try:
        return asdict(TaskStore(db).propose(
            tenant_id=actor.tenant_id, action=data.action,
            assignee_id=str(data.assignee_id),
        ))
    except ValueError as exc:
        translate_error(exc)


@router.post("/tasks/{task_id}/approval")
def attach_approval(
    task_id: UUID, data: ApprovalLink, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "task:create")
    try:
        TaskStore(db).request_approval(
            task_id=str(task_id), tenant_id=actor.tenant_id,
            approval_id=str(data.approval_id),
        )
    except (PermissionError, ValueError) as exc:
        translate_error(exc)
    return {"status": "waiting_approval"}


@router.post("/tasks/{task_id}/start")
def start_task(
    task_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    try:
        task = TaskStore(db).authorize_and_start(
            task_id=str(task_id), principal=actor
        )
        return asdict(task)
    except (PermissionError, ValueError) as exc:
        translate_error(exc)


@router.post("/tasks/{task_id}/finish")
def finish_task(
    task_id: UUID, data: FinishInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "task:execute")
    try:
        TaskStore(db).finish(
            task_id=str(task_id), tenant_id=actor.tenant_id,
            success=data.success,
        )
    except ValueError as exc:
        translate_error(exc)
    return {"status": "completed" if data.success else "failed"}


@router.post("/tasks/{task_id}/review")
def review_task(
    task_id: UUID, data: ReviewInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    try:
        review = QualityStore(db).review(
            task_id=str(task_id), principal=actor,
            verdict=data.verdict, evidence=data.evidence,
        )
        return asdict(review)
    except (PermissionError, ValueError) as exc:
        translate_error(exc)


@router.post("/memory")
def save_memory(
    data: MemoryInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "memory:write")
    try:
        record = MemoryRecord.create(
            tenant_id=actor.tenant_id, owner_id=actor.subject,
            content=data.content, visibility=data.visibility,
        )
        MemoryStore(db).save(record)
        return {"id": record.id, "visibility": record.visibility}
    except ValueError as exc:
        translate_error(exc)


@router.get("/memory/{record_id}")
def get_memory(
    record_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "memory:read")
    try:
        record = MemoryStore(db).get(
            record_id=str(record_id), tenant_id=actor.tenant_id,
            reader_id=actor.subject,
        )
        return asdict(record)
    except (PermissionError, LookupError) as exc:
        translate_error(exc)
