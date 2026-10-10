"""M5 virtual economy, scorecards, risk scenarios and proposals API."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import Field

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import CreditBudgetPort, ExperimentStorePort, ScorecardPort
from ago.security import Principal
from ago.simulation import ScenarioSimulator

router = APIRouter(prefix="/v1/insights", tags=["M5 economics and simulation"])


class BudgetInput(StrictInput):
    ceiling: Decimal = Field(gt=0, le=1_000_000_000)


class UsageInput(StrictInput):
    operation_key: str = Field(min_length=1, max_length=180)
    amount: Decimal = Field(gt=0, le=1_000_000_000)
    category: str = Field(min_length=1, max_length=100)


class ScenarioInput(StrictInput):
    planned_actions: int = Field(ge=0, le=1_000_000)
    cost_per_action: Decimal = Field(gt=0, le=1_000_000_000)
    failure_percent: int = Field(default=0, ge=0, le=100)


class ExperimentInput(StrictInput):
    hypothesis: str = Field(min_length=1, max_length=2000)
    baseline: str = Field(min_length=1, max_length=2000)
    candidate: str = Field(min_length=1, max_length=2000)


@router.post("/budget")
def set_budget(
    data: BudgetInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "economy:manage")
    try:
        repositories.resolve(CreditBudgetPort).configure(
            tenant_id=actor.tenant_id, ceiling=data.ceiling
        )
        return repositories.resolve(CreditBudgetPort).balance(tenant_id=actor.tenant_id)
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/usage")
def record_usage(
    data: UsageInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "economy:consume")
    try:
        return repositories.resolve(CreditBudgetPort).charge(
            tenant_id=actor.tenant_id,
            actor_id=actor.subject,
            operation_key=data.operation_key,
            amount=data.amount,
            category=data.category,
        )
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/scorecard")
def scorecard(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "insights:read")
    return repositories.resolve(ScorecardPort).summary(tenant_id=actor.tenant_id)


@router.post("/simulate")
def simulate(
    data: ScenarioInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "simulation:run")
    budget = repositories.resolve(CreditBudgetPort).balance(tenant_id=actor.tenant_id)
    try:
        return ScenarioSimulator.estimate(
            planned_actions=data.planned_actions,
            cost_per_action=data.cost_per_action,
            available_credits=budget["remaining"],
            failure_percent=data.failure_percent,
        )
    except ValueError as exc:
        translate_error(exc)


@router.post("/experiments")
def propose_experiment(
    data: ExperimentInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "experiments:propose")
    try:
        return repositories.resolve(ExperimentStorePort).propose(
            tenant_id=actor.tenant_id,
            proposer_id=actor.subject,
            hypothesis=data.hypothesis,
            baseline=data.baseline,
            candidate=data.candidate,
        )
    except ValueError as exc:
        translate_error(exc)


@router.get("/experiments")
def list_experiments(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "experiments:read")
    return repositories.resolve(ExperimentStorePort).list(tenant_id=actor.tenant_id)
