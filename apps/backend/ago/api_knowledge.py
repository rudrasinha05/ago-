"""M6 evidence-backed knowledge graph API; no automatic policy execution."""

from __future__ import annotations

import base64
import binascii
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import Field, StrictBool, StrictInt

from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.repository_ports import DatabaseStorePort, KnowledgeStorePort, MessageStorePort, SemanticMemoryStorePort
from ago.security import Principal
from ago.storage_adapters import StorageUnavailable

router = APIRouter(prefix="/v1/knowledge", tags=["M6 knowledge"])


class MessageInput(StrictInput):
    kind: Literal['command', 'event', 'query', 'notification', 'approval']
    name: str = Field(min_length=3, max_length=100)
    payload: dict
    operation_key: str = Field(min_length=1, max_length=150)
    ordering_key: str = Field(default='default', min_length=1, max_length=150)
    correlation_id: UUID | None = None


class ReplayInput(StrictInput):
    reason: str = Field(min_length=1, max_length=500)


class MemoryInput(StrictInput):
    scope: Literal['employee', 'department', 'project', 'company']
    scope_id: UUID
    kind: Literal['episodic', 'working']
    content: str = Field(min_length=1, max_length=12000)
    source_ref: str = Field(min_length=1, max_length=1000)
    retention_hours: StrictInt | None = Field(default=None, ge=1, le=8760)
    knowledge_id: UUID | None = None


class ConsolidateInput(StrictInput):
    memory_ids: list[UUID] = Field(min_length=2, max_length=20)


class CorrectionInput(StrictInput):
    content: str = Field(min_length=1, max_length=12000)
    expected_revision: StrictInt = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class ProjectMemberInput(StrictInput):
    user_id: UUID
    member: StrictBool


@router.post('/memory')
def create_memory(data: MemoryInput, actor: Principal = Depends(authenticated),
                  db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).create(actor=actor, scope=data.scope,
            scope_id=str(data.scope_id), kind=data.kind, content=data.content, source_ref=data.source_ref,
            retention_hours=data.retention_hours if data.retention_hours is not None else (24 if data.kind == 'working' else 2160),
            knowledge_id=str(data.knowledge_id) if data.knowledge_id else None)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get('/memory/{memory_id}')
def get_memory(memory_id: UUID, actor: Principal = Depends(authenticated),
               db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).get(actor=actor, memory_id=str(memory_id))
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post('/memory/{memory_id}/index')
def index_memory(memory_id: UUID, actor: Principal = Depends(authenticated),
                 db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).index(actor=actor, memory_id=str(memory_id))
    except (ValueError, PermissionError, LookupError, StorageUnavailable, OSError) as exc:
        storage_error(exc)


@router.post('/memory/search')
def search_memory(data: SearchInput, actor: Principal = Depends(authenticated),
                  db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).search(actor=actor, query=data.query, limit=data.limit)
    except (ValueError, PermissionError, LookupError, StorageUnavailable, OSError) as exc:
        storage_error(exc)


@router.post('/memory/consolidate')
def consolidate_memory(data: ConsolidateInput, actor: Principal = Depends(authenticated),
                       db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).consolidate(actor=actor, memory_ids=[str(i) for i in data.memory_ids])
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post('/memory/{memory_id}/correct')
def correct_memory(memory_id: UUID, data: CorrectionInput, actor: Principal = Depends(authenticated),
                   db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).correct(actor=actor, memory_id=str(memory_id),
            content=data.content, expected_revision=data.expected_revision, reason=data.reason)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post('/memory/{memory_id}/forget')
def forget_memory(memory_id: UUID, data: ReplayInput, actor: Principal = Depends(authenticated),
                  db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).forget(actor=actor, memory_id=str(memory_id), reason=data.reason)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post('/memory/expire')
def expire_memory(actor: Principal = Depends(authenticated), db=Depends(db_connection),
                  repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).expire(actor=actor)
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post('/memory/projects/{goal_id}/members')
def memory_member(goal_id: UUID, data: ProjectMemberInput, actor: Principal = Depends(authenticated),
                  db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    try:
        return repositories.resolve(SemanticMemoryStorePort).set_project_member(actor=actor, goal_id=str(goal_id),
                                                                              user_id=str(data.user_id), member=data.member)
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.post('/messages')
def publish_message(data: MessageInput, actor: Principal = Depends(authenticated),
                    db=Depends(db_connection), repositories: RepositoryScope = Depends(repository_scope)):
    allowed(repositories, actor, 'messages:write')
    try:
        return repositories.resolve(MessageStorePort).publish(
            actor=actor, kind=data.kind, name=data.name, payload=data.payload,
            operation_key=data.operation_key, ordering_key=data.ordering_key,
            correlation_id=str(data.correlation_id) if data.correlation_id else None)
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get('/messages')
def inspect_messages(limit: int = Query(default=100, ge=1, le=200),
                     actor: Principal = Depends(authenticated), db=Depends(db_connection),
                     repositories: RepositoryScope = Depends(repository_scope)):
    allowed(repositories, actor, 'messages:read')
    store = repositories.resolve(MessageStorePort)
    return {'messages': store.inspect(tenant_id=actor.tenant_id, limit=limit),
            'metrics': store.metrics(tenant_id=actor.tenant_id)}


@router.post('/messages/{message_id}/replay')
def replay_message(message_id: UUID, data: ReplayInput,
                   actor: Principal = Depends(authenticated), db=Depends(db_connection),
                   repositories: RepositoryScope = Depends(repository_scope)):
    try:
        replayed = repositories.resolve(MessageStorePort).replay(
            actor=actor, message_id=str(message_id), reason=data.reason)
        if not replayed:
            raise HTTPException(404, 'Dead message not found')
        return {'id': str(message_id), 'status': 'pending'}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


class NodeInput(StrictInput):
    kind: str
    label: str = Field(min_length=1, max_length=250)
    statement: str = Field(min_length=1, max_length=12000)
    source_ref: str = Field(min_length=1, max_length=1000)


class ReviewInput(StrictInput):
    approve: StrictBool
    note: str = Field(min_length=1, max_length=3000)


class EdgeInput(StrictInput):
    from_id: UUID
    to_id: UUID
    relation: str


@router.post("/nodes")
def propose(
    data: NodeInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "knowledge:write")
    try:
        identifier = repositories.resolve(KnowledgeStorePort).propose(
            actor=actor,
            kind=data.kind,
            label=data.label,
            statement=data.statement,
            source_ref=data.source_ref,
        )
        return {"id": identifier, "status": "pending"}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/nodes")
def verified(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "knowledge:read")
    return repositories.resolve(KnowledgeStorePort).verified(tenant_id=actor.tenant_id)


@router.get("/pending")
def pending(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "knowledge:review")
    return repositories.resolve(KnowledgeStorePort).pending(tenant_id=actor.tenant_id)


@router.post("/nodes/{node_id}/review")
def review(
    node_id: UUID,
    data: ReviewInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    try:
        return repositories.resolve(KnowledgeStorePort).review(
            actor=actor,
            node_id=str(node_id),
            approve=data.approve,
            note=data.note,
        )
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.post("/edges")
def relate(
    data: EdgeInput,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "knowledge:write")
    try:
        identifier = repositories.resolve(KnowledgeStorePort).relate(
            actor=actor,
            from_id=str(data.from_id),
            to_id=str(data.to_id),
            relation=data.relation,
        )
        return {"id": identifier}
    except (ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/nodes/{node_id}/edges")
def edges(
    node_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "knowledge:read")
    return repositories.resolve(KnowledgeStorePort).edges(
        tenant_id=actor.tenant_id, node_id=str(node_id)
    )


class DocumentInput(StrictInput):
    filename: str = Field(min_length=1, max_length=250)
    media_type: Literal['text/plain', 'application/pdf', 'application/octet-stream']
    content_base64: str = Field(min_length=4, max_length=699052)
    retention_days: StrictInt = Field(default=90, ge=1, le=365)


class SearchInput(StrictInput):
    query: str = Field(min_length=1, max_length=1000)
    limit: StrictInt = Field(default=10, ge=1, le=50)


def storage_error(exc):
    # PermissionError inherits OSError: preserve authorization status first.
    if isinstance(exc, PermissionError):
        translate_error(exc)
    if isinstance(exc, (StorageUnavailable, OSError)):
        raise HTTPException(503, 'Knowledge storage unavailable') from exc
    translate_error(exc)


@router.get('/nodes/{node_id}/graph')
def graph(
    node_id: UUID,
    depth: int = Query(default=2, ge=0, le=4),
    limit: int = Query(default=100, ge=1, le=200),
    direction: Literal['both', 'out', 'in'] = 'both',
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, 'knowledge:read')
    try:
        return repositories.resolve(DatabaseStorePort).graph(
            tenant_id=actor.tenant_id, root_id=str(node_id), depth=depth,
            limit=limit, direction=direction)
    except (ValueError, LookupError, StorageUnavailable, OSError) as exc:
        storage_error(exc)


@router.post('/nodes/{node_id}/index')
def index_node(
    node_id: UUID,
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, 'knowledge:write')
    try:
        return repositories.resolve(DatabaseStorePort).index_node(
            tenant_id=actor.tenant_id, node_id=str(node_id))
    except (ValueError, LookupError, StorageUnavailable, OSError) as exc:
        storage_error(exc)


@router.post('/search')
def semantic_search(
    data: SearchInput,
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, 'knowledge:read')
    try:
        return repositories.resolve(DatabaseStorePort).search(
            tenant_id=actor.tenant_id, query=data.query, limit=data.limit)
    except (ValueError, StorageUnavailable, OSError) as exc:
        storage_error(exc)


@router.post('/documents')
def upload_document(
    data: DocumentInput,
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, 'knowledge:write')
    try:
        content = base64.b64decode(data.content_base64, validate=True)
        return repositories.resolve(DatabaseStorePort).upload(
            actor=actor, filename=data.filename, media_type=data.media_type,
            content=content, retention_days=data.retention_days)
    except binascii.Error as exc:
        raise HTTPException(400, 'Invalid document encoding') from exc
    except (ValueError, StorageUnavailable, OSError) as exc:
        storage_error(exc)


@router.get('/documents')
def documents(
    limit: int = Query(default=100, ge=1, le=200),
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, 'knowledge:read')
    return repositories.resolve(DatabaseStorePort).documents(tenant_id=actor.tenant_id, limit=limit)


@router.get('/documents/{object_id}')
def download_document(
    object_id: UUID,
    actor: Principal = Depends(authenticated),
    db=Depends(db_connection),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, 'knowledge:read')
    try:
        metadata, content = repositories.resolve(DatabaseStorePort).download(
            tenant_id=actor.tenant_id, object_id=str(object_id))
        return Response(content, media_type='application/octet-stream', headers={
            'Content-Disposition': f'attachment; filename="{object_id}.bin"',
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'X-Object-SHA256': metadata['sha256'],
        })
    except (ValueError, LookupError, StorageUnavailable, OSError) as exc:
        storage_error(exc)
