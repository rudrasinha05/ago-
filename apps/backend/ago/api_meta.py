"""M7 Meta Brain and Organizational DNA authenticated HTTP API.

This router does not execute policies, tools, code or organizational changes.
"""

from __future__ import annotations

from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import ConfigDict, Field

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import (
    ApprovalRepositoryPort, ExecutiveIntelligencePort, GenomeStorePort, MetaBrainPort,
)
from ago.security import Principal

router = APIRouter(prefix="/v1/meta", tags=["M7 Meta Brain"])


class DNAThresholds(StrictInput):
    model_config = ConfigDict(extra="forbid")

    qa_target_pct: int = Field(ge=50, le=100)
    backlog_limit: int = Field(ge=0, le=10000)
    budget_alert_pct: int = Field(ge=1, le=100)


class DNACandidate(StrictInput):
    model_config = ConfigDict(extra="forbid")
    profile: DNAThresholds
    rationale: str = Field(min_length=1, max_length=3000)
    charter: dict[str, str] | None = None
    scope_kind: Literal["company", "department", "employee"] = "company"
    scope_id: UUID | None = None


class ScenarioInput(StrictInput):
    snapshot_id: UUID
    profile: DNAThresholds


def call(operation):
    try:
        return operation()
    except (ValueError, LookupError, PermissionError) as exc:
        translate_error(exc)


@router.get("/dna")
def versions(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:dna:read")
    return repositories.resolve(GenomeStorePort).list(tenant_id=actor.tenant_id)


@router.get("/dna/active")
def active_dna(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:dna:read")
    return repositories.resolve(GenomeStorePort).active(tenant_id=actor.tenant_id)


@router.post("/dna")
def propose_dna(
    data: DNACandidate,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:dna:propose")
    return call(
        lambda: repositories.resolve(GenomeStorePort).propose(
            tenant_id=actor.tenant_id,
            proposer_id=actor.subject,
            profile=data.profile.model_dump(),
            rationale=data.rationale, charter=data.charter,
            scope_kind=data.scope_kind, scope_id=str(data.scope_id) if data.scope_id else None,
        )
    )


@router.post("/dna/{dna_id}/reconcile")
def reconcile_dna(
    dna_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:dna:activate")
    return call(
        lambda: repositories.resolve(GenomeStorePort).reconcile(
            tenant_id=actor.tenant_id,
            genome_id=str(dna_id),
        )
    )


@router.post("/snapshots")
def capture(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:observe")
    return repositories.resolve(ExecutiveIntelligencePort).capture(
        tenant_id=actor.tenant_id,
        analyst_id=actor.subject,
    )


@router.get("/snapshots")
def snapshots(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(ExecutiveIntelligencePort).list(tenant_id=actor.tenant_id)


@router.get("/snapshots/{snapshot_id}")
def snapshot(
    snapshot_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return call(
        lambda: repositories.resolve(ExecutiveIntelligencePort).get(
            tenant_id=actor.tenant_id,
            snapshot_id=str(snapshot_id),
        )
    )


@router.post("/simulate")
def simulate(
    data: ScenarioInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:simulate")
    return call(
        lambda: repositories.resolve(ExecutiveIntelligencePort).simulate(
            tenant_id=actor.tenant_id,
            snapshot_id=str(data.snapshot_id),
            candidate=data.profile.model_dump(),
        )
    )


@router.post("/snapshots/{snapshot_id}/recommendations")
def generate(
    snapshot_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:recommend")
    return call(
        lambda: repositories.resolve(MetaBrainPort).generate(
            tenant_id=actor.tenant_id,
            author_id=actor.subject,
            snapshot_id=str(snapshot_id),
        )
    )


@router.get("/recommendations")
def recommendations(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(MetaBrainPort).list(tenant_id=actor.tenant_id)


@router.post("/recommendations/{recommendation_id}/reconcile")
def reconcile_recommendation(
    recommendation_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:finalize")
    return call(
        lambda: repositories.resolve(MetaBrainPort).reconcile(
            tenant_id=actor.tenant_id,
            recommendation_id=str(recommendation_id),
        )
    )


@router.get("/brief")
def executive_brief(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(MetaBrainPort).brief(tenant_id=actor.tenant_id)


@router.get("/snapshots/{snapshot_id}/verify")
def verify_snapshot(
    snapshot_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return call(
        lambda: repositories.resolve(ExecutiveIntelligencePort).verify(
            tenant_id=actor.tenant_id,
            snapshot_id=str(snapshot_id),
        )
    )


class EvaluationInput(StrictInput):
    recommendation_id: UUID
    after_id: UUID
    change_evidence: str = Field(min_length=1, max_length=3000)


class ArchitectureInput(StrictInput):
    change_key: str = Field(pattern=r"^ARCH-[0-9]{3,8}$")
    specification: dict


@router.get("/dna/effective")
def effective_dna(
    department_id: UUID | None = None, employee_id: UUID | None = None,
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:dna:read")
    return call(lambda: repositories.resolve(GenomeStorePort).effective(
        tenant_id=actor.tenant_id, department_id=str(department_id) if department_id else None,
        employee_id=str(employee_id) if employee_id else None))


@router.get("/reflection")
def reflection(
    limit: int = Query(default=20, ge=2, le=100),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return call(lambda: repositories.resolve(MetaBrainPort).reflect(tenant_id=actor.tenant_id, limit=limit))


@router.post("/evaluations")
def propose_evaluation(
    data: EvaluationInput, actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:recommend")
    return call(lambda: repositories.resolve(MetaBrainPort).propose_evaluation(
        tenant_id=actor.tenant_id, author_id=actor.subject,
        recommendation_id=str(data.recommendation_id), after_id=str(data.after_id),
        change_evidence=data.change_evidence))


@router.get("/evaluations")
def evaluations(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:read")
    return repositories.resolve(MetaBrainPort).evaluations(tenant_id=actor.tenant_id)


@router.post("/evaluations/{evaluation_id}/reconcile")
def finalize_evaluation(
    evaluation_id: UUID, actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "meta:finalize")
    return call(lambda: repositories.resolve(MetaBrainPort).reconcile_evaluation(
        tenant_id=actor.tenant_id, evaluation_id=str(evaluation_id)))


@router.post("/architecture/changes")
def propose_architecture(
    data: ArchitectureInput, actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    return call(lambda: repositories.resolve(ApprovalRepositoryPort).propose_architecture(
        tenant_id=actor.tenant_id, requester_id=actor.subject,
        change_key=data.change_key, specification=data.specification))


@router.get("/architecture/changes")
def architecture_changes(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "approval:read")
    return repositories.resolve(ApprovalRepositoryPort).architecture_changes(tenant_id=actor.tenant_id)


@router.post("/architecture/changes/{change_id}/reconcile")
def finalize_architecture(
    change_id: UUID, actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "brain:manage")
    return call(lambda: repositories.resolve(ApprovalRepositoryPort).reconcile_architecture(
        tenant_id=actor.tenant_id, change_id=str(change_id)))
