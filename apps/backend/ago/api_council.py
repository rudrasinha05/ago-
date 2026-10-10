"""M6 executive council: only independent authenticated humans vote."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import CouncilStorePort
from ago.security import Principal

router = APIRouter(prefix="/v1/council", tags=["M6 executive council"])


class MotionInput(StrictInput):
    title: str = Field(min_length=1, max_length=250)
    rationale: str = Field(min_length=1, max_length=6000)
    required_votes: int = Field(default=2, ge=2, le=10)


class VoteInput(StrictInput):
    vote: str
    reason: str = Field(min_length=1, max_length=3000)


@router.post("/motions")
def propose(
    data: MotionInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "council:propose")
    try:
        return repositories.resolve(CouncilStorePort).propose(
            actor=actor,
            title=data.title,
            rationale=data.rationale,
            required_votes=data.required_votes,
        )
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/motions")
def motions(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "council:read")
    return repositories.resolve(CouncilStorePort).list(tenant_id=actor.tenant_id)


@router.post("/motions/{motion_id}/votes")
def vote(
    motion_id: UUID,
    data: VoteInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(CouncilStorePort).vote(
            actor=actor,
            motion_id=str(motion_id),
            vote=data.vote,
            reason=data.reason,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/motions/{motion_id}/votes")
def ballots(
    motion_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "council:read")
    return repositories.resolve(CouncilStorePort).ballots(
        tenant_id=actor.tenant_id,
        motion_id=str(motion_id),
    )


@router.post("/motions/{motion_id}/finalize")
def finalize(
    motion_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        status = repositories.resolve(CouncilStorePort).finalize(
            actor=actor, motion_id=str(motion_id)
        )
        return {"id": str(motion_id), "status": status, "execution_permitted": False}
    except (PermissionError, LookupError) as exc:
        translate_error(exc)
