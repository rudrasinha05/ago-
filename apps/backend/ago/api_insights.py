"""M5 virtual economy, scorecards, risk scenarios and proposals API."""
from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ago.api_m2 import allowed, authenticated, db_connection, translate_error
from ago.credits import CreditBudget
from ago.experiments import ExperimentStore
from ago.scorecard import Scorecard
from ago.security import Principal
from ago.simulation import ScenarioSimulator

router = APIRouter(prefix="/v1/insights", tags=["M5 economics and simulation"])


class BudgetInput(BaseModel):
    ceiling: Decimal = Field(gt=0, le=1_000_000_000)


class UsageInput(BaseModel):
    operation_key: str = Field(min_length=1, max_length=180)
    amount: Decimal = Field(gt=0, le=1_000_000_000)
    category: str = Field(min_length=1, max_length=100)


class ScenarioInput(BaseModel):
    planned_actions: int = Field(ge=0, le=1_000_000)
    cost_per_action: Decimal = Field(gt=0, le=1_000_000_000)
    failure_percent: int = Field(default=0, ge=0, le=100)


class ExperimentInput(BaseModel):
    hypothesis: str = Field(min_length=1, max_length=2000)
    baseline: str = Field(min_length=1, max_length=2000)
    candidate: str = Field(min_length=1, max_length=2000)


@router.post("/budget")
def set_budget(data: BudgetInput, db=Depends(db_connection),
               actor: Principal = Depends(authenticated)):
    allowed(db, actor, "economy:manage")
    try:
        CreditBudget(db).configure(tenant_id=actor.tenant_id, ceiling=data.ceiling)
        return CreditBudget(db).balance(tenant_id=actor.tenant_id)
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post("/usage")
def record_usage(data: UsageInput, db=Depends(db_connection),
                 actor: Principal = Depends(authenticated)):
    allowed(db, actor, "economy:consume")
    try:
        return CreditBudget(db).charge(
            tenant_id=actor.tenant_id, actor_id=actor.subject,
            operation_key=data.operation_key, amount=data.amount,
            category=data.category,
        )
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/scorecard")
def scorecard(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "insights:read")
    return Scorecard(db).summary(tenant_id=actor.tenant_id)


@router.post("/simulate")
def simulate(data: ScenarioInput, db=Depends(db_connection),
             actor: Principal = Depends(authenticated)):
    allowed(db, actor, "simulation:run")
    budget = CreditBudget(db).balance(tenant_id=actor.tenant_id)
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
def propose_experiment(data: ExperimentInput, db=Depends(db_connection),
                       actor: Principal = Depends(authenticated)):
    allowed(db, actor, "experiments:propose")
    try:
        return ExperimentStore(db).propose(
            tenant_id=actor.tenant_id, proposer_id=actor.subject,
            hypothesis=data.hypothesis, baseline=data.baseline,
            candidate=data.candidate,
        )
    except ValueError as exc:
        translate_error(exc)


@router.get("/experiments")
def list_experiments(db=Depends(db_connection),
                     actor: Principal = Depends(authenticated)):
    allowed(db, actor, "experiments:read")
    return ExperimentStore(db).list(tenant_id=actor.tenant_id)
