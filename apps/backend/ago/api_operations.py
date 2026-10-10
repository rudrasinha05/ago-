"""M6 departmental handoff and calendar API with signed-session RBAC."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import CalendarStorePort, HandoffStorePort
from ago.security import Principal

router = APIRouter(prefix="/v1/operations", tags=["M6 operations"])


class HandoffInput(StrictInput):
    sender_department_id: UUID
    receiver_department_id: UUID
    assignee_id: UUID
    title: str = Field(min_length=1, max_length=250)
    brief: str = Field(min_length=1, max_length=6000)
    operation_key: str = Field(min_length=1, max_length=160)


class HandoffDecision(StrictInput):
    decision: str
    note: str = Field(min_length=1, max_length=6000)


class CalendarInput(StrictInput):
    title: str = Field(min_length=1, max_length=250)
    detail: str = Field(default="", max_length=6000)
    starts_at: datetime
    ends_at: datetime
    visibility: str = "tenant"
    operation_key: str = Field(min_length=1, max_length=160)
    employee_ids: list[UUID] = Field(default_factory=list, max_length=100)
    goal_id: UUID | None = None
    task_id: UUID | None = None


class RSVPInput(StrictInput):
    response: str


@router.post("/handoffs")
def request_handoff(
    data: HandoffInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:request")
    try:
        identifier = repositories.resolve(HandoffStorePort).request(
            actor=actor,
            sender_department_id=str(data.sender_department_id),
            receiver_department_id=str(data.receiver_department_id),
            assignee_id=str(data.assignee_id),
            title=data.title,
            brief=data.brief,
            operation_key=data.operation_key,
        )
        return {"id": identifier, "status": "requested"}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/handoffs/{handoff_id}/transition")
def transition_handoff(
    handoff_id: UUID,
    data: HandoffDecision,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(HandoffStorePort).transition(
            actor=actor,
            handoff_id=str(handoff_id),
            decision=data.decision,
            note=data.note,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/handoffs")
def handoffs(
    department_id: UUID | None = None,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return repositories.resolve(HandoffStorePort).list(
        tenant_id=actor.tenant_id,
        department_id=str(department_id) if department_id else None,
    )


@router.get("/handoffs/{handoff_id}/history")
def handoff_history(
    handoff_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return repositories.resolve(HandoffStorePort).history(
        tenant_id=actor.tenant_id,
        handoff_id=str(handoff_id),
    )


@router.post("/calendar")
def schedule_event(
    data: CalendarInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "calendar:write")
    try:
        identifier = repositories.resolve(CalendarStorePort).schedule(
            actor=actor,
            title=data.title,
            detail=data.detail,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            visibility=data.visibility,
            operation_key=data.operation_key,
            employee_ids=[str(x) for x in data.employee_ids],
            goal_id=str(data.goal_id) if data.goal_id else None,
            task_id=str(data.task_id) if data.task_id else None,
        )
        return {"id": identifier}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/calendar")
def calendar(
    start: datetime,
    end: datetime,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "calendar:read")
    try:
        return repositories.resolve(CalendarStorePort).list(actor=actor, start=start, end=end)
    except ValueError as exc:
        translate_error(exc)


@router.post("/calendar/{event_id}/cancel")
def cancel_event(
    event_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "calendar:write")
    try:
        repositories.resolve(CalendarStorePort).cancel(actor=actor, event_id=str(event_id))
        return {"status": "cancelled"}
    except (PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/calendar/{event_id}/rsvp")
def rsvp(
    event_id: UUID,
    data: RSVPInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "calendar:respond")
    try:
        repositories.resolve(CalendarStorePort).respond(
            actor=actor,
            event_id=str(event_id),
            response=data.response,
        )
        return {"response": data.response}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/calendar/{event_id}/attendees")
def calendar_attendees(
    event_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "calendar:read")
    try:
        return repositories.resolve(CalendarStorePort).attendees(
            actor=actor, event_id=str(event_id)
        )
    except PermissionError as exc:
        translate_error(exc)


@router.get("/calendar/{event_id}/history")
def calendar_history(
    event_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "calendar:read")
    try:
        return repositories.resolve(CalendarStorePort).history(actor=actor, event_id=str(event_id))
    except PermissionError as exc:
        translate_error(exc)


# Sections 21–27: authorized application calls only, never SQL in transport.
from typing import Literal
from decimal import Decimal
from fastapi import Query
from ago.repository_ports import EnterpriseOperationsStorePort, ApprovalRepositoryPort


class EnterpriseModeApproval(StrictInput):
    target: Literal["active", "paused", "maintenance", "emergency", "suspended"]
    scope_kind: Literal["company", "department", "employee"] = "company"
    scope_id: UUID | None = None


class EnterpriseModeChange(EnterpriseModeApproval):
    approval_id: UUID
    rationale: str = Field(min_length=1, max_length=3000)
    expires_at: datetime


class AgentCapacity(StrictInput):
    available_units: int = Field(ge=0, le=100000)
    source_ref: str = Field(min_length=1, max_length=1024)


class EnterprisePlanApproval(StrictInput):
    # Returned plan ID is bound to the exact independently approved action.
    pass


class EnterprisePlanInput(StrictInput):
    plan_id: UUID
    approval_id: UUID
    parent_id: UUID | None = None
    horizon: Literal["lifetime", "five_year", "annual", "quarterly", "monthly",
                     "weekly", "daily", "hourly", "current_task"]
    title: str = Field(min_length=1, max_length=300)
    starts_at: datetime
    ends_at: datetime
    budget_ceiling: Decimal = Field(ge=0)
    evidence_ref: str = Field(min_length=1, max_length=1024)


class EnterpriseCostInput(StrictInput):
    operation_key: str = Field(min_length=1, max_length=200)
    category: Literal["model","storage","tool","execution","time","revenue","other"]
    provider: str = Field(min_length=1, max_length=180)
    source_ref: str = Field(min_length=1, max_length=1024)
    amount: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: datetime
    period_end: datetime


class EnterpriseBudgetInput(StrictInput):
    budget_id: UUID
    approval_id: UUID
    scope_kind: Literal["company", "department", "employee"]
    scope_id: UUID | None = None
    ceiling: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class EnterpriseAssetInput(StrictInput):
    department_id: UUID
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["service", "library", "dataset", "research", "design_system",
                  "template", "agent", "model", "workflow"]
    version: str = Field(pattern=r"^[0-9]+[.][0-9]+[.][0-9]+$")
    license_id: str = Field(min_length=1, max_length=200)
    sha256_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest: dict = Field(default_factory=dict)


class ApprovalReference(StrictInput):
    approval_id: UUID


class AssetConsumption(ApprovalReference):
    department_id: UUID
    evidence_ref: str = Field(min_length=1, max_length=1024)


class EvolutionComparison(StrictInput):
    snapshot_id: UUID
    baseline: list[str] = Field(min_length=1, max_length=1000)
    candidate: list[str] = Field(min_length=1, max_length=1000)
    evidence: list[dict] = Field(min_length=1, max_length=1000)


class EnterpriseTwinInput(StrictInput):
    snapshot_id: UUID
    actions: int = Field(ge=0, le=100000)
    cost_per_action: Decimal = Field(ge=0)
    budget: Decimal = Field(ge=0)
    failure_pct: int = Field(ge=0, le=100)
    hiring: int = Field(ge=0, le=100000, default=0)
    layoffs: int = Field(ge=0, le=100000, default=0)
    market_shock_pct: int = Field(ge=-100, le=100, default=0)


def enterprise_call(fn):
    try:
        return fn()
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


def issue_enterprise_approval(repositories, actor, action: str) -> dict:
    allowed(repositories, actor, "approval:request")
    approval = repositories.resolve(ApprovalRepositoryPort).propose(
        tenant_id=actor.tenant_id, action=action, requester_id=actor.subject
    )
    return {"approval_id": approval.request_id, "action": action, "status": "pending"}


@router.get("/enterprise/modes")
def enterprise_modes(
    scope_kind: Literal["company", "department", "employee"] = "company",
    scope_id: UUID | None = None,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    store = repositories.resolve(EnterpriseOperationsStorePort)
    return enterprise_call(lambda: {
        "effective": store.effective_mode(tenant_id=actor.tenant_id, scope_kind=scope_kind,
                                         scope_id=str(scope_id) if scope_id else None),
        "history": store.modes(tenant_id=actor.tenant_id, scope_kind=scope_kind,
                               scope_id=str(scope_id) if scope_id else None),
    })


@router.post("/enterprise/modes/approval")
def request_mode_approval(
    data: EnterpriseModeApproval,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    if (data.scope_kind == "company") != (data.scope_id is None):
        return enterprise_call(lambda: (_ for _ in ()).throw(ValueError("Invalid scope")))
    action = "enterprise:mode:" + data.scope_kind + ":" + (
        str(data.scope_id) if data.scope_id else "company") + ":" + data.target
    return issue_enterprise_approval(repositories, actor, action)


@router.post("/enterprise/modes/activate")
def activate_enterprise_mode(
    data: EnterpriseModeChange,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).mode_change(
        actor=actor, target=data.target, approval_id=str(data.approval_id),
        reason=data.rationale, expires_at=data.expires_at, scope_kind=data.scope_kind,
        scope_id=str(data.scope_id) if data.scope_id else None,
    ))


@router.get("/enterprise/agents/{employee_id}/state")
def enterprise_agent_state(
    employee_id: UUID,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).worker_state(
        tenant_id=actor.tenant_id, employee_id=str(employee_id)))


@router.post("/enterprise/agents/{employee_id}/snapshot")
def enterprise_agent_snapshot(
    employee_id: UUID, data: AgentCapacity,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).capture_worker(
        actor=actor, employee_id=str(employee_id), available_units=data.available_units,
        source_ref=data.source_ref))


@router.post("/enterprise/agents/{employee_id}/allocation")
def enterprise_allocation(
    employee_id: UUID, data: AgentCapacity,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).allocate_preview(
        tenant_id=actor.tenant_id, employee_id=str(employee_id),
        available_units=data.available_units))


@router.post("/enterprise/plans/approval")
def enterprise_plan_approval(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    from uuid import uuid4
    identifier = str(uuid4())
    return {"plan_id": identifier, **issue_enterprise_approval(
        repositories, actor, "enterprise:plan:" + identifier)}


@router.post("/enterprise/plans")
def create_enterprise_plan(
    data: EnterprisePlanInput,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).plan(
        actor=actor, identifier=str(data.plan_id), horizon=data.horizon,
        parent_id=str(data.parent_id) if data.parent_id else None,
        title=data.title, starts_at=data.starts_at, ends_at=data.ends_at,
        budget_ceiling=str(data.budget_ceiling), approval_id=str(data.approval_id),
        evidence_ref=data.evidence_ref))


@router.get("/enterprise/plans")
def list_enterprise_plans(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return repositories.resolve(EnterpriseOperationsStorePort).plans(tenant_id=actor.tenant_id)


@router.post("/enterprise/costs")
def record_enterprise_cost(
    data: EnterpriseCostInput,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).record_cost(
        actor=actor, operation_key=data.operation_key, category=data.category,
        provider=data.provider, source_ref=data.source_ref, amount=str(data.amount),
        currency=data.currency, period_start=data.period_start,
        period_end=data.period_end))


@router.get("/enterprise/costs")
def list_enterprise_costs(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(EnterpriseOperationsStorePort).costs(tenant_id=actor.tenant_id)


@router.post("/enterprise/budgets/approval")
def enterprise_budget_approval(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    from uuid import uuid4
    identifier = str(uuid4())
    return {"budget_id": identifier, **issue_enterprise_approval(
        repositories, actor, "enterprise:budget:" + identifier)}


@router.post("/enterprise/budgets")
def create_enterprise_budget(
    data: EnterpriseBudgetInput,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).create_budget(
        actor=actor, identifier=str(data.budget_id), approval_id=str(data.approval_id),
        scope_kind=data.scope_kind, scope_id=str(data.scope_id) if data.scope_id else None,
        ceiling=str(data.ceiling), currency=data.currency))


@router.get("/enterprise/budgets")
def list_enterprise_budgets(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(EnterpriseOperationsStorePort).budgets(tenant_id=actor.tenant_id)


@router.post("/enterprise/marketplace")
def create_marketplace_draft(
    data: EnterpriseAssetInput,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).asset_draft(
        actor=actor, department_id=str(data.department_id), name=data.name, kind=data.kind,
        version=data.version, license_id=data.license_id, digest=data.sha256_digest,
        manifest=data.manifest))


@router.get("/enterprise/marketplace")
def discover_marketplace(
    kind: str | None = None,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).assets(
        tenant_id=actor.tenant_id, kind=kind))


@router.post("/enterprise/marketplace/{asset_id}/approval")
def request_marketplace_review(
    asset_id: UUID,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    reference = issue_enterprise_approval(repositories, actor,
                                           "enterprise:publish:" + str(asset_id))
    result = enterprise_call(lambda: repositories.resolve(
        EnterpriseOperationsStorePort).asset_propose(
        actor=actor, asset_id=str(asset_id), approval_id=reference["approval_id"]))
    return {**reference, **result}


@router.post("/enterprise/marketplace/{asset_id}/publish")
def publish_marketplace_asset(
    asset_id: UUID,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(
        EnterpriseOperationsStorePort).asset_publish(actor=actor, asset_id=str(asset_id)))


@router.post("/enterprise/marketplace/{asset_id}/consume/approval")
def marketplace_consume_review(
    asset_id: UUID,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:request")
    return issue_enterprise_approval(repositories, actor,
                                     "enterprise:consume:" + str(asset_id))


@router.post("/enterprise/marketplace/{asset_id}/consume")
def consume_marketplace_asset(
    asset_id: UUID, data: AssetConsumption,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:request")
    return enterprise_call(lambda: repositories.resolve(
        EnterpriseOperationsStorePort).asset_consume(
        actor=actor, asset_id=str(asset_id), department_id=str(data.department_id),
        approval_id=str(data.approval_id), evidence_ref=data.evidence_ref))


@router.get("/enterprise/marketplace/usage")
def marketplace_consumptions(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(EnterpriseOperationsStorePort).asset_usage(
        tenant_id=actor.tenant_id)


@router.post("/enterprise/evolution/compare")
def compare_evolution(
    data: EvolutionComparison,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:observe")
    return enterprise_call(lambda: repositories.resolve(
        EnterpriseOperationsStorePort).evolution_observation(
        actor=actor, baseline=data.baseline, candidate=data.candidate,
        evidence=data.evidence, source_snapshot_id=str(data.snapshot_id)))


@router.post("/enterprise/twin")
def simulate_enterprise_twin(
    data: EnterpriseTwinInput,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:simulate")
    return enterprise_call(lambda: repositories.resolve(EnterpriseOperationsStorePort).twin(
        actor=actor, snapshot_id=str(data.snapshot_id), actions=data.actions,
        cost_per_action=str(data.cost_per_action), budget=str(data.budget),
        failure_pct=data.failure_pct, hiring=data.hiring, layoffs=data.layoffs,
        market_shock_pct=data.market_shock_pct))


@router.get("/enterprise/twin")
def enterprise_twin_history(
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(EnterpriseOperationsStorePort).twin_runs(
        tenant_id=actor.tenant_id)


class EnterpriseWorkerApproval(StrictInput):
    state: Literal["available","idle","paused","sleeping","interrupted","unavailable","terminated"]


class EnterpriseWorkerTransition(EnterpriseWorkerApproval):
    approval_id: UUID
    reason: str = Field(min_length=1, max_length=3000)
    expires_at: datetime | None = None


class EnterpriseAssetLifecycleApproval(StrictInput):
    target_state: Literal["deprecated", "revoked"]


class EnterpriseAssetLifecycle(EnterpriseAssetLifecycleApproval):
    approval_id: UUID
    reason: str = Field(min_length=1, max_length=3000)


@router.get("/enterprise/agents/{employee_id}/history")
def enterprise_worker_history(
    employee_id: UUID,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "operations:read")
    return repositories.resolve(EnterpriseOperationsStorePort).worker_history(
        tenant_id=actor.tenant_id, employee_id=str(employee_id))


@router.post("/enterprise/agents/{employee_id}/approval")
def enterprise_worker_approval(
    employee_id: UUID, data: EnterpriseWorkerApproval,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return issue_enterprise_approval(
        repositories, actor, "enterprise:worker:" + str(employee_id) + ":" + data.state)


@router.post("/enterprise/agents/{employee_id}/transition")
def enterprise_worker_transition(
    employee_id: UUID, data: EnterpriseWorkerTransition,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(
        EnterpriseOperationsStorePort).worker_transition(
        actor=actor, employee_id=str(employee_id), state=data.state,
        approval_id=str(data.approval_id), reason=data.reason,
        expires_at=data.expires_at))


@router.post("/enterprise/marketplace/{asset_id}/lifecycle/approval")
def enterprise_asset_retirement_approval(
    asset_id: UUID, data: EnterpriseAssetLifecycleApproval,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return issue_enterprise_approval(
        repositories, actor, "enterprise:asset:" + str(asset_id) + ":" + data.target_state)


@router.post("/enterprise/marketplace/{asset_id}/lifecycle")
def enterprise_asset_retirement(
    asset_id: UUID, data: EnterpriseAssetLifecycle,
    db=Depends(db_connection), actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "organization:manage")
    return enterprise_call(lambda: repositories.resolve(
        EnterpriseOperationsStorePort).asset_retire(
        actor=actor, asset_id=str(asset_id), target_state=data.target_state,
        approval_id=str(data.approval_id), reason=data.reason))
