"""M7 Meta Brain and Organizational DNA authenticated HTTP API.

This router does not execute policies, tools, code or organizational changes.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import ConfigDict, Field

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import ExecutiveIntelligencePort, GenomeStorePort, MetaBrainPort
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
            rationale=data.rationale,
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
