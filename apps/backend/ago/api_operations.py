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
