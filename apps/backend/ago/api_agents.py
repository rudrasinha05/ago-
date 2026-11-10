"""M4 governed AI worker APIs. No unsafe runtime tools exposed."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.company_engineering_preflight import inspect_engineering_task
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.model_handlers import optional_model_handlers
from ago.repository_ports import (
    AgentRuntimePort, AiQaReviewPort, CalendarStorePort, CompanyChatPort,
    ConsoleServicePort, StageProgressionPort,
)
from ago.security import Principal
from ago.stage_progression import next_step

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


# --------------------------------------------------------------------------
# PROJ-006 / ACC-152: one server-side "advance this project" operation.
#
# The browser used to choose and call each step itself, so a project moved only
# while a page was open. Here the SERVER chooses the one next step and performs
# it through the same governed services the single-step endpoints use:
#
#     request approval -> AI hierarchy approval -> self-check + run -> AI QA
#     -> AI manager decision (open next stage / recover a failed stage)
#
# It is an ordinary signed Founder request: authentication, token revocation,
# constitution and emergency containment are enforced by the shared dependency,
# and the work calendar is checked here before a run, exactly as for /run. It
# grants nothing new and never replays a run: a task whose outcome is unknown
# is reported back for the Founder instead of being touched.
# --------------------------------------------------------------------------

# Steps after which nothing can happen until a person acts.
FOUNDER_STEPS = {
    "unstaffed": "The {stage} stage has no approved AI worker; staff it first.",
    "rejected": "The {stage} task approval was rejected; the Founder decides what to do.",
    "unknown": "The {stage} stage is in a state AGO cannot advance automatically.",
}


def _chain_enabled() -> bool:
    return (os.getenv("AGO_LLM_PROVIDER") == "ollama_local"
            and os.getenv("AGO_ENABLE_LOCAL_MODELS") == "true"
            and os.getenv("AGO_LOCAL_COMPANY_CHAIN") == "true")


def _outcome(step: dict, *, progressed: bool, needs_founder: bool, message: str,
             done: bool = False, **extra) -> dict:
    return {
        "kind": "ago_project_advance_v1", "step": step["step"], "stage": step.get("stage"),
        "task_id": step.get("task_id"), "progressed": progressed, "done": done,
        "needs_founder": needs_founder, "message": message, **extra,
    }


def _manager(step: dict, decision: dict) -> dict:
    acted = decision.get("action") in ("opened_stage", "recovered_stage")
    return _outcome(
        step, progressed=acted, needs_founder=bool(decision.get("needs_founder")),
        message=(
            str(decision.get("decided_by_name")) + " (AI project manager) "
            + ("opened the " + str(decision.get("stage")) + " stage and assigned its task."
               if decision.get("action") == "opened_stage"
               else "created a new " + str(decision.get("stage")) + " task: "
               + str(decision.get("reason")))
            if acted else str(decision.get("reason"))),
        decision=decision,
    )


def advance_once(db, actor: Principal, repositories: RepositoryScope, project_id: str) -> dict:
    """Choose and perform exactly one step. Raises only for bad requests."""
    detail = repositories.resolve(CompanyChatPort).project_details(
        actor.tenant_id, project_id, reader_id=actor.subject)
    if detail["plan_status"] != "active":
        return _outcome({"step": "inactive"}, progressed=False, needs_founder=True,
                        message="The project plan is not approved and active.")
    step = next_step(detail["stages"])
    kind, stage, task_id = step["step"], step.get("stage"), step.get("task_id")
    if kind == "done":
        return _outcome(step, progressed=False, needs_founder=False, done=True,
                        message="Every stage passed independent AI QA.")
    if kind in FOUNDER_STEPS:
        return _outcome(step, progressed=False, needs_founder=True,
                        message=FOUNDER_STEPS[kind].format(stage=stage))
    if kind == "running":
        return _outcome(step, progressed=False, needs_founder=False,
                        message="The " + stage + " task is running; waiting for it to finish.")
    if kind in ("open_stage", "recover"):
        return _manager(step, repositories.resolve(StageProgressionPort).continue_project(
            tenant_id=actor.tenant_id, founder_id=actor.subject, project_id=project_id))
    try:
        if kind == "request":
            allowed(repositories, actor, "task:create")
            allowed(repositories, actor, "approval:request")
            repositories.resolve(ConsoleServicePort).request_approval(task_id, actor)
            return _outcome(step, progressed=True, needs_founder=False,
                            message="Approval requested for the " + stage + " task.")
        if kind == "approve":
            done = repositories.resolve(CompanyChatPort).ceo_reconcile(actor, project_id)
            who = next((a for a in done.get("task_approvers") or []
                        if a.get("task_id") == task_id), None)
            if who is None:
                return _outcome(
                    step, progressed=False, needs_founder=True,
                    message="The AI team could not approve the " + stage
                            + " task; the Founder decides it in Approvals.")
            return _outcome(
                step, progressed=True, needs_founder=False,
                message=str(who["approver_name"]) + " (" + str(who["approver_level"]).replace(
                    "_", " ") + ") approved the " + stage + " task and is responsible for it.")
        if kind == "run":
            return _run(db, actor, repositories, step)
        return _qa(actor, repositories, project_id, step)
    except PermissionError as exc:
        # A refused step is a reason for the Founder, not a crash of the advance.
        return _outcome(step, progressed=False, needs_founder=True, message=str(exc))


def _run(db, actor, repositories, step) -> dict:
    stage, task_id = step["stage"], step["task_id"]
    allowed(repositories, actor, "agent:dispatch")
    repositories.resolve(CalendarStorePort).require_execution(actor=actor, task_id=task_id)
    if _chain_enabled():
        # Same read-only self-check the Founder sees: never burn an approved
        # task on a run that the hierarchy or the credit allowance would stop.
        report = inspect_engineering_task(
            db, tenant_id=actor.tenant_id, founder_id=actor.subject, task_id=task_id)
        if report["blocking_checks"]:
            return _outcome(
                step, progressed=False, needs_founder=True,
                message="Self-check blocked the " + stage + " run: "
                        + ", ".join(report["blocking_checks"]),
                blocking_checks=report["blocking_checks"])
    handlers = {**BUILTIN_HANDLERS, **optional_model_handlers(db, actor, repositories=repositories)}
    try:
        ran = repositories.resolve(AgentRuntimePort, handlers=handlers).run(
            task_id=task_id, actor=actor)
    except RuntimeError:
        # The failure and its safe code are recorded; the AI manager was
        # already asked. The next advance reads the new state.
        return _outcome(step, progressed=True, needs_founder=False, run_status="failed",
                        message="The " + stage + " run failed; the recorded reason decides "
                                "the next step.")
    blocked = ran.get("delivery_status") == "blocked"
    return _outcome(
        step, progressed=True, needs_founder=False,
        run_status=ran.get("status"), delivery_status=ran.get("delivery_status"),
        message=("The Board stopped the " + stage + " run; the AI manager will revise and "
                 "resubmit it." if blocked
                 else "The AI team finished the " + stage + " task; the result is recorded."))


def _qa(actor, repositories, project_id, step) -> dict:
    stage = step["stage"]
    try:
        review = repositories.resolve(AiQaReviewPort).review_stage(
            tenant_id=actor.tenant_id, founder_id=actor.subject, project_id=project_id,
            stage=stage, operation_key=str(uuid4()))
    except PermissionError:
        raise  # a refusal (e.g. no independent tester), not a failed model call
    except (TimeoutError, OSError, RuntimeError):
        return _outcome(step, progressed=False, needs_founder=False, qa_verdict=None,
                        message="The AI QA model call failed for " + stage
                                + "; no QA verdict was returned. The attempt may have consumed "
                                "a virtual credit. The next advance checks recorded state "
                                "before retrying.")
    verdict = review["verdict"]
    return _outcome(
        step, progressed=verdict in ("pass", "fail"), needs_founder=False, qa_verdict=verdict,
        qa_employee_name=review["qa_employee_name"], decision=review.get("continuation"),
        message=("AI QA by " + review["qa_employee_name"] + ": " + verdict.upper() + " for "
                 + stage + "." if verdict in ("pass", "fail")
                 else "AI QA gave no clear verdict for " + stage
                      + "; the review receipt and one virtual-credit charge were recorded."))


@router.post("/projects/{project_id}/advance")
def advance_project(project_id: UUID, db=Depends(db_connection),
                    actor: Principal = Depends(authenticated),
                    repositories: RepositoryScope = Depends(repository_scope)):
    """Founder: the server does the ONE next governed step of this project."""
    allowed(repositories, actor, "organization:read")
    allowed(repositories, actor, "approval:founder")
    if "founder" not in actor.roles:
        translate_error(PermissionError("Only the project Founder may advance a project"))
    try:
        return advance_once(db, actor, repositories, str(project_id))
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)
