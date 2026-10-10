"""M8 trusted enterprise tool, enrollment, automation and evidence API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ago.api_m2 import allowed, authenticated, db_connection, translate_error
from ago.department_automation import DepartmentAutomation
from ago.security import Principal
from ago.tool_catalog import TOOL_DESCRIPTIONS
from ago.tool_enrollment import ToolEnrollment
from ago.tool_runtime import EnterpriseToolRuntime

router = APIRouter(prefix="/v1/tools", tags=["M8 Enterprise Tools"])


class EnrollmentInput(BaseModel):
    code: str
    rationale: str = Field(min_length=1, max_length=3000)


class DisableInput(BaseModel):
    reason: str = Field(min_length=1, max_length=3000)


class AutomationInput(BaseModel):
    department_id: UUID
    assignee_id: UUID
    code: str
    trigger: str


class FiringInput(BaseModel):
    source_id: UUID


class ScanInput(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)


def call(operation):
    try:
        return operation()
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/catalog")
def catalog(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "tool:read")
    return [
        {"code": key, "description": value}
        for key, value in TOOL_DESCRIPTIONS.items()
    ]


@router.post("/enrollments")
def propose_enrollment(
    data: EnrollmentInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:enroll")
    return call(lambda: ToolEnrollment(db).propose(
        actor=actor, code=data.code, rationale=data.rationale,
    ))


@router.get("/enrollments")
def enrollments(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:read")
    return ToolEnrollment(db).list(tenant_id=actor.tenant_id)


@router.get("/enrollments/{enrollment_id}/history")
def enrollment_history(
    enrollment_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:read")
    return ToolEnrollment(db).history(
        tenant_id=actor.tenant_id, enrollment_id=str(enrollment_id),
    )


@router.post("/enrollments/{enrollment_id}/reconcile")
def reconcile_enrollment(
    enrollment_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:enroll")
    return call(lambda: ToolEnrollment(db).reconcile(
        actor=actor, enrollment_id=str(enrollment_id),
    ))


@router.post("/enrollments/{enrollment_id}/disable")
def disable_enrollment(
    enrollment_id: UUID, data: DisableInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:enroll")
    return call(lambda: ToolEnrollment(db).disable(
        actor=actor, enrollment_id=str(enrollment_id),
        reason=data.reason,
    ))


@router.post("/automation/rules")
def create_rule(
    data: AutomationInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "automation:manage")
    return call(lambda: {
        "id": DepartmentAutomation(db).create(
            actor=actor, department_id=str(data.department_id),
            assignee_id=str(data.assignee_id),
            code=data.code, trigger=data.trigger,
        ), "status": "active",
    })


@router.get("/automation/rules")
def rules(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "automation:read")
    return DepartmentAutomation(db).list_rules(tenant_id=actor.tenant_id)


@router.post("/automation/rules/{rule_id}/disable")
def disable_rule(
    rule_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "automation:manage")
    return call(lambda: (
        DepartmentAutomation(db).disable(
            tenant_id=actor.tenant_id, rule_id=str(rule_id),
        ) or {"id": str(rule_id), "status": "disabled"}
    ))


@router.post("/automation/rules/{rule_id}/fire")
def fire(
    rule_id: UUID, data: FiringInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "automation:run")
    return call(lambda: DepartmentAutomation(db).fire(
        tenant_id=actor.tenant_id, rule_id=str(rule_id),
        source_id=str(data.source_id),
    ))


@router.post("/automation/scan")
def scan(
    data: ScanInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "automation:run")
    return call(lambda: {
        "firings": DepartmentAutomation(db).scan(
            tenant_id=actor.tenant_id, limit=data.limit,
        ), "automatic_execution": False,
    })


@router.get("/automation/firings")
def firings(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "automation:read")
    return DepartmentAutomation(db).list_firings(tenant_id=actor.tenant_id)


@router.post("/tasks/{task_id}/run")
def execute(
    task_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:dispatch")
    try:
        return EnterpriseToolRuntime(db).run(task_id=str(task_id), actor=actor)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)
    except RuntimeError as exc:
        raise HTTPException(502, "Governed enterprise tool failed") from exc


@router.get("/runs")
def runs(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "tool:read")
    return EnterpriseToolRuntime(db).list(tenant_id=actor.tenant_id)


@router.get("/runs/{run_id}/evidence")
def run_evidence(
    run_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:read")
    return EnterpriseToolRuntime(db).evidence(
        tenant_id=actor.tenant_id, run_id=str(run_id),
    )


@router.post("/runs/recover-stale")
def recover_stale(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "tool:recover")
    return {
        "uncertain_runs": EnterpriseToolRuntime(db).recover_stale(
            tenant_id=actor.tenant_id,
        ), "manual_reconciliation_required": True,
    }
