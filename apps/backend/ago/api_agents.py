"""M4 governed AI worker APIs. No unsafe runtime tools exposed."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.model_handlers import optional_model_handlers
from ago.repository_ports import AgentRuntimePort
from ago.security import Principal

router = APIRouter(prefix="/v1/agents", tags=["M4 workforce"])


@router.get("/runs")
def runs(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "agent:read")
    return repositories.resolve(AgentRuntimePort).list(tenant_id=actor.tenant_id)


@router.post("/tasks/{task_id}/run")
def execute(
    task_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "agent:dispatch")
    handlers = {**BUILTIN_HANDLERS, **optional_model_handlers(db, actor, repositories=repositories)}
    try:
        return repositories.resolve(AgentRuntimePort, handlers=handlers).run(
            task_id=str(task_id),
            actor=actor,
        )
    except (PermissionError, ValueError) as exc:
        translate_error(exc)
    except RuntimeError as exc:
        raise HTTPException(502, "Agent handler failed") from exc


@router.post("/recover-stale")
def recover_stale(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "agent:recover")
    return {
        "failed_runs": repositories.resolve(AgentRuntimePort).recover_stale(
            tenant_id=actor.tenant_id
        ),
        "manual_reconciliation_required": True,
    }
