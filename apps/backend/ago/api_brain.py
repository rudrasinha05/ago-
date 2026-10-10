"""M3 session- and RBAC-protected Company Brain API."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import GoalStorePort, PlanExecutionPort, PlanStorePort
from ago.security import Principal

router = APIRouter(prefix="/v1/brain", tags=["M3 Company Brain"])


class GoalInput(StrictInput):
    title: str = Field(min_length=1, max_length=250)
    description: str = ""
    parent_id: UUID | None = None


class PlanInput(StrictInput):
    goal_id: UUID
    title: str = Field(min_length=1, max_length=250)


class StepInput(StrictInput):
    action: str = Field(min_length=1, max_length=500)
    assignee_id: UUID
    depends_on: UUID | None = None


@router.post("/goals")
def create_goal(
    data: GoalInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    try:
        goal_id = repositories.resolve(GoalStorePort).create(
            tenant_id=actor.tenant_id,
            created_by=actor.subject,
            title=data.title,
            description=data.description,
            parent_id=str(data.parent_id) if data.parent_id else None,
        )
        return {"id": goal_id}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/goals")
def list_goals(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:read")
    return repositories.resolve(GoalStorePort).list(tenant_id=actor.tenant_id)


@router.post("/plans")
def create_plan(
    data: PlanInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    try:
        plan_id = repositories.resolve(PlanStorePort).create(
            tenant_id=actor.tenant_id,
            proposer_id=actor.subject,
            goal_id=str(data.goal_id),
            title=data.title,
        )
        return {"id": plan_id}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/plans")
def list_plans(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:read")
    return repositories.resolve(PlanStorePort).list(tenant_id=actor.tenant_id)


@router.post("/plans/{plan_id}/steps")
def add_step(
    plan_id: UUID,
    data: StepInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    try:
        return {
            "id": repositories.resolve(PlanStorePort).add_step(
                tenant_id=actor.tenant_id,
                plan_id=str(plan_id),
                action=data.action,
                assignee_id=str(data.assignee_id),
                depends_on=str(data.depends_on) if data.depends_on else None,
            )
        }
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/plans/{plan_id}/steps")
def list_steps(
    plan_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:read")
    return repositories.resolve(PlanStorePort).steps(
        tenant_id=actor.tenant_id, plan_id=str(plan_id)
    )


@router.post("/plans/{plan_id}/submit")
def submit_plan(
    plan_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    try:
        approval_id = repositories.resolve(PlanStorePort).submit(
            tenant_id=actor.tenant_id, plan_id=str(plan_id), requester_id=actor.subject
        )
        return {"approval_id": approval_id, "status": "pending_approval"}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/plans/{plan_id}/activate")
def activate(
    plan_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:activate")
    try:
        repositories.resolve(PlanExecutionPort).activate(
            tenant_id=actor.tenant_id, plan_id=str(plan_id)
        )
        return {"status": "active"}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/plans/{plan_id}/materialize")
def materialize(
    plan_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:activate")
    try:
        ids = repositories.resolve(PlanExecutionPort).materialize(
            tenant_id=actor.tenant_id, plan_id=str(plan_id)
        )
        return {"task_ids": ids, "approval_required_per_task": True}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


class GoalClose(StrictInput):
    status: Literal["completed", "cancelled"]


@router.post("/goals/{goal_id}/close")
def close_goal(
    goal_id: UUID,
    data: GoalClose,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    try:
        repositories.resolve(GoalStorePort).close(
            tenant_id=actor.tenant_id, goal_id=str(goal_id), status=data.status
        )
        return {"status": data.status}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)
