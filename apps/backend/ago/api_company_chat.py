"""Authenticated company map and shared conversation endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import Field
from ago.api_contracts import StrictInput
from ago.api_m2 import allowed, authenticated, repository_scope, translate_error
from ago.repository_ports import CompanyChatPort

router = APIRouter(prefix='/v1/organization/company', tags=['Company map'])


class ChatInput(StrictInput):
    channel: str = Field(default='global', max_length=80)
    body: str = Field(min_length=1, max_length=20000)
    reply_to: int | None = Field(default=None, gt=0)
    operation_key: UUID


@router.get('/chat')
def timeline(channel: str = 'global', before: int | None = Query(default=None, gt=0),
             limit: int = Query(default=60, ge=1, le=200),
             actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    allowed(repositories, actor, 'messages:read')
    try:
        return repositories.resolve(CompanyChatPort).list(actor.tenant_id, channel, before, limit)
    except ValueError as exc:
        translate_error(exc)


@router.post('/chat')
def send(data: ChatInput, actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    allowed(repositories, actor, 'messages:write')
    try:
        return repositories.resolve(CompanyChatPort).send(
            actor, data.channel, data.body, data.reply_to, str(data.operation_key))
    except ValueError as exc:
        translate_error(exc)


@router.get('/activity')
def activity(actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'brain:read')
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    return repositories.resolve(CompanyChatPort).activity(actor.tenant_id)

    
@router.get('/notifications')
def notifications(actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:read')
    allowed(repositories, actor, 'task:read')
    return repositories.resolve(CompanyChatPort).notifications(actor.tenant_id)


class StaffingInput(StrictInput):
    department_id: UUID
    manager_id: UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    requirement: str = Field(min_length=10, max_length=3000)
    operation_key: UUID


@router.post('/staffing')
def staff(data: StaffingInput, actor=Depends(authenticated), repositories=Depends(repository_scope)):
    allowed(repositories, actor, 'organization:manage')
    allowed(repositories, actor, 'task:read')
    allowed(repositories, actor, 'messages:write')
    try:
        return repositories.resolve(CompanyChatPort).staff(
            actor, str(data.department_id), str(data.manager_id) if data.manager_id else None,
            data.name, data.requirement, str(data.operation_key))
    except (ValueError, PermissionError) as exc:
        translate_error(exc)
