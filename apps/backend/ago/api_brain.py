"""M3 session- and RBAC-protected Company Brain API."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from ago.api_m2 import allowed, authenticated, db_connection, translate_error
from ago.goals import GoalStore
from ago.plan_store import PlanStore
from ago.plan_execution import PlanExecution
from ago.security import Principal

router = APIRouter(prefix="/v1/brain", tags=["M3 Company Brain"])

class GoalInput(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str = ""
    parent_id: UUID | None = None

class PlanInput(BaseModel):
    goal_id: UUID
    title: str = Field(min_length=1, max_length=250)

class StepInput(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    assignee_id: UUID
    depends_on: UUID | None = None

@router.post("/goals")
def create_goal(data: GoalInput, db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "brain:manage")
    try:
        goal_id = GoalStore(db).create(
            tenant_id=actor.tenant_id, created_by=actor.subject,
            title=data.title, description=data.description,
            parent_id=str(data.parent_id) if data.parent_id else None,
        )
        return {"id": goal_id}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)

@router.get("/goals")
def list_goals(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "brain:read")
    return GoalStore(db).list(tenant_id=actor.tenant_id)

@router.post("/plans")
def create_plan(data: PlanInput, db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "brain:manage")
    try:
        plan_id = PlanStore(db).create(
            tenant_id=actor.tenant_id, proposer_id=actor.subject,
            goal_id=str(data.goal_id), title=data.title,
        )
        return {"id": plan_id}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)

@router.get("/plans")
def list_plans(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "brain:read")
    return PlanStore(db).list(tenant_id=actor.tenant_id)

@router.post("/plans/{plan_id}/steps")
def add_step(plan_id: UUID, data: StepInput, db=Depends(db_connection),
             actor: Principal = Depends(authenticated)):
    allowed(db, actor, "brain:manage")
    try:
        return {"id": PlanStore(db).add_step(
            tenant_id=actor.tenant_id, plan_id=str(plan_id), action=data.action,
            assignee_id=str(data.assignee_id),
            depends_on=str(data.depends_on) if data.depends_on else None)}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)

@router.get('/plans/{plan_id}/steps')
def list_steps(plan_id: UUID, db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, 'brain:read')
    return PlanStore(db).steps(tenant_id=actor.tenant_id, plan_id=str(plan_id))
