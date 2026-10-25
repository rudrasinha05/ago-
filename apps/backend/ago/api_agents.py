"""M4 governed AI worker APIs. No unsafe runtime tools exposed."""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.company_engineering_preflight import inspect_engineering_task
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.model_handlers import optional_model_handlers
from ago.repository_ports import AgentRuntimePort
from ago.security import Principal

router = APIRouter(prefix="/v1/agents", tags=["M4 workforce"])


def local_engineering_status() -> dict:
    """Configuration truth only: never infer an active model or approved task."""
    local = (
        os.getenv("AGO_ENVIRONMENT", "development").lower()
        in ("development", "test", "testing")
        and os.getenv("AGO_LLM_PROVIDER") == "ollama_local"
        and os.getenv("AGO_ENABLE_LOCAL_MODELS") == "true"
        and os.getenv("AGO_LOCAL_COMPANY_CHAIN") == "true"
        and os.getenv("AGO_LOCAL_FULL_BOARD_REVIEW") == "true"
        and os.getenv("AGO_LOCAL_ENGINEERING_CANDIDATES") == "true"
        and bool(os.getenv("AGO_LLM_MODEL"))
        and os.getenv("AGO_ENABLE_PAID_MODELS") != "true"
    )
    return {
        "kind": "ago_local_engineering_capabilities",
        "engineering_enabled": local,
        "provider_mode": "ollama_local" if local else "disabled",
        "required_roles": 7,
        "model_tag": os.getenv("AGO_LLM_MODEL") if local else None,
        "model_inference_verified": False,
        "board_or_task_approval_verified": False,
        "github_write_authorized": False,
        "release_ready": False,
    }


@router.get("/engineering-capabilities")
def engineering_capabilities(
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "agent:read")
    allowed(repositories, actor, "approval:founder")
    return local_engineering_status()


@router.get("/runs")
def runs(
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    allowed(repositories, actor, "agent:read")
    # Result evidence can contain founder project excerpts. A generic employee
    # agent:read role must never expose other confidential projects.
    allowed(repositories, actor, "approval:founder")
    return repositories.resolve(AgentRuntimePort).list(tenant_id=actor.tenant_id)


@router.get("/tasks/{task_id}/engineering-preflight")
def engineering_preflight(
    task_id: UUID,
    db=Depends(db_connection),
    actor: Principal = Depends(authenticated),
    repositories: RepositoryScope = Depends(repository_scope),
):
    """Founder-only GET; SQL read-only transaction and no model/task dispatch."""
    allowed(repositories, actor, "agent:read")
    allowed(repositories, actor, "approval:founder")
    if os.getenv("AGO_ENVIRONMENT", "development").lower() not in (
        "development", "test", "testing"
    ):
        raise HTTPException(403, "Local engineering diagnostics require development mode")
    with db.transaction():
        return inspect_engineering_task(
            db, tenant_id=actor.tenant_id, founder_id=actor.subject,
            task_id=str(task_id), set_read_only=True,
        )


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
