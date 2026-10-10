"""M6 evidence-backed knowledge graph API; no automatic policy execution."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ago.api_m2 import allowed, authenticated, db_connection, translate_error
from ago.knowledge_store import KnowledgeStore
from ago.security import Principal

router = APIRouter(prefix="/v1/knowledge", tags=["M6 knowledge"])


class NodeInput(BaseModel):
    kind: str
    label: str = Field(min_length=1, max_length=250)
    statement: str = Field(min_length=1, max_length=12000)
    source_ref: str = Field(min_length=1, max_length=1000)


class ReviewInput(BaseModel):
    approve: bool
    note: str = Field(min_length=1, max_length=3000)


class EdgeInput(BaseModel):
    from_id: UUID
    to_id: UUID
    relation: str


@router.post("/nodes")
def propose(
    data: NodeInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "knowledge:write")
    try:
        identifier = KnowledgeStore(db).propose(
            actor=actor, kind=data.kind, label=data.label,
            statement=data.statement, source_ref=data.source_ref,
        )
        return {"id": identifier, "status": "pending"}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/nodes")
def verified(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "knowledge:read")
    return KnowledgeStore(db).verified(tenant_id=actor.tenant_id)


@router.get("/pending")
def pending(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "knowledge:review")
    return KnowledgeStore(db).pending(tenant_id=actor.tenant_id)


@router.post("/nodes/{node_id}/review")
def review(
    node_id: UUID, data: ReviewInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    try:
        return KnowledgeStore(db).review(
            actor=actor, node_id=str(node_id),
            approve=data.approve, note=data.note,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/edges")
def relate(
    data: EdgeInput, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "knowledge:write")
    try:
        identifier = KnowledgeStore(db).relate(
            actor=actor, from_id=str(data.from_id), to_id=str(data.to_id),
            relation=data.relation,
        )
        return {"id": identifier}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/nodes/{node_id}/edges")
def edges(
    node_id: UUID, db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
):
    allowed(db, actor, "knowledge:read")
    return KnowledgeStore(db).edges(tenant_id=actor.tenant_id, node_id=str(node_id))
