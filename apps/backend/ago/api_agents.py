"""M4 governed AI worker APIs. No unsafe runtime tools exposed."""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.agent_runtime import AgentRuntime
from ago.api_m2 import allowed, authenticated, db_connection, translate_error
from ago.security import Principal

router = APIRouter(prefix="/v1/agents", tags=["M4 workforce"])


@router.get("/runs")
def runs(db=Depends(db_connection), actor: Principal = Depends(authenticated)):
    allowed(db, actor, "agent:read")
    return AgentRuntime(db).list(tenant_id=actor.tenant_id)


@router.post("/tasks/{task_id}/run")
def execute(task_id: UUID, db=Depends(db_connection),
            actor: Principal = Depends(authenticated)):
    allowed(db, actor, "agent:dispatch")
    try:
        return AgentRuntime(db, handlers=BUILTIN_HANDLERS).run(
            task_id=str(task_id), actor=actor,
        )
    except (PermissionError, ValueError) as exc:
        translate_error(exc)
