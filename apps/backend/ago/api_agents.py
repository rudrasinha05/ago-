"""M4 governed AI worker APIs. No unsafe runtime tools exposed."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.company_engineering_preflight import inspect_engineering_task
from ago.api_m2 import allowed, authenticated, db_connection, repository_scope, translate_error
from ago.backend_contracts import RepositoryScope
from ago.model_handlers import local_model_unavailable, optional_model_handlers
from ago.repository_ports import (
    AgentRuntimePort, AiQaReviewPort, CalendarStorePort, CompanyChatPort,
    ConsoleServicePort, IntegrationStorePort, StageProgressionPort,
)
from ago.security import Principal
from ago.stage_progression import STAGES, RevisionConflict, next_step

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
            (str(decision.get("recovery_decided_by_name")) + " (AI CEO) "
             if decision.get("recovery_decided_by_level") in ("ceo", "ceo_changed_approach")
             else str(decision.get("decided_by_name")) + " (AI project manager) ")
            + ("opened the " + str(decision.get("stage")) + " stage and assigned its task."
               if decision.get("action") == "opened_stage"
               else "created a new " + str(decision.get("stage")) + " task: "
               + str(decision.get("reason")))
            if acted else str(decision.get("reason"))),
        decision=decision,
    )


def advance_once(db, actor: Principal, repositories: RepositoryScope, project_id: str) -> dict:
    """One owner-scoped, serialized step with durable routing of every refusal."""
    detail = repositories.resolve(CompanyChatPort).project_details(
        actor.tenant_id, project_id, reader_id=actor.subject)
    router = repositories.resolve(StageProgressionPort)
    with router.advance_guard(tenant_id=actor.tenant_id, project_id=project_id) as acquired:
        if not acquired:
            return _outcome({'step': 'running'}, progressed=False, needs_founder=False,
                            message='Another request is advancing this project; waiting for its result.')
        started = datetime.now(timezone.utc)
        reply = _advance_once(db, actor, repositories, project_id)
        if reply['progressed'] and reply.get('stage') in STAGES:
            # Close only blockers older than this step; a failure this step
            # recorded (e.g. a credit problem) stays visible.
            router.resolve_stage_blockers(tenant_id=actor.tenant_id, project_id=project_id,
                                          stage=reply['stage'], before=started)
        unclear = reply['step'] == 'qa' and not reply['progressed'] and not reply.get('scheduled')
        if (reply['needs_founder'] or reply.get('schedule_at') or unclear) and not (
                reply.get('followup') or (reply.get('decision') or {}).get('followup')):
            stage = reply.get('stage') or next_step(detail['stages']).get('stage') or 'discovery'
            kind = reply['step']
            owner = ('manager' if reply.get('failure_code') in (
                         'test_runner_unavailable', 'model_runner_unavailable') else
                     'worker' if reply.get('schedule_at') else
                     'ceo' if kind == 'unstaffed' else
                     'quality' if kind == 'qa' else
                     'founder' if kind in ('inactive', 'rejected', 'unknown') else 'manager')
            checks = reply.get('blocking_checks') or []
            if any('credit' in c for c in checks) or str(reply.get('failure_code') or '').startswith('credit_'):
                owner = 'founder'
            reply['followup'] = router.route_followup(
                tenant_id=actor.tenant_id, founder_id=actor.subject, project_id=project_id,
                stage=stage, code=(reply['failure_code'] if reply.get('failure_code')
                                  else 'calendar_wait' if reply.get('schedule_at')
                                  else 'qa_unavailable' if kind == 'qa'
                                  else kind + '_blocked'),
                feedback=reply['message'], source_task_id=reply.get('task_id'),
                owner_kind=owner, blocked=reply['needs_founder'],
                eligible_at=reply.get('schedule_at'))
        return reply


def _advance_once(db, actor: Principal, repositories: RepositoryScope, project_id: str) -> dict:
    """Choose and perform exactly one step. Raises only for bad requests."""
    detail = repositories.resolve(CompanyChatPort).project_details(
        actor.tenant_id, project_id, reader_id=actor.subject)
    if detail["plan_status"] != "active":
        return _outcome({"step": "inactive"}, progressed=False, needs_founder=True,
                        message="The project plan is not approved and active.")
    step = next_step(detail["stages"])
    kind, stage, task_id = step["step"], step.get("stage"), step.get("task_id")
    if kind in ('run', 'qa'):
        scheduled = repositories.resolve(StageProgressionPort).scheduled_work(
            tenant_id=actor.tenant_id, project_id=project_id, task_id=task_id)
        if scheduled:
            return _outcome(step, progressed=False, needs_founder=False,
                            message='Work assigned to ' + scheduled['owner_name'] + '; scheduled for '
                                    + scheduled['eligible_at'].isoformat() + '.',
                            followup=scheduled, scheduled=True)
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
        if kind == "qa":
            tested = _test_candidate(actor, repositories, project_id, step)
            if tested is not None:
                return tested
        if kind in ("run", "qa"):
            down = local_model_unavailable()
            if down is not None:
                # A machine problem, not a defect of the work: no run starts, no
                # attempt is spent, nobody is called. Try again in 5 minutes.
                return _outcome(step, progressed=False, needs_founder=False,
                                failure_code="model_runner_unavailable",
                                schedule_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                                message="The " + stage + " work waits: " + down
                                        + " AGO will try again in 5 minutes.")
        if kind == "run":
            assigned = next(s for s in detail['stages'] if str(s.get('task_id')) == task_id)
            return _run(db, actor, repositories, {**step, 'assignee_id':
                        assigned.get('approved_assignee_id') or assigned.get('suggested_assignee_id')})
        return _qa(actor, repositories, project_id, step)
    except PermissionError as exc:
        # A refused step is a reason for the Founder, not a crash of the advance.
        return _outcome(step, progressed=False, needs_founder=True, message=str(exc),
                        failure_code=getattr(exc, 'failure_code', None))


def _run(db, actor, repositories, step) -> dict:
    stage, task_id = step["stage"], step["task_id"]
    allowed(repositories, actor, "agent:dispatch")
    calendar = repositories.resolve(CalendarStorePort)
    try:
        calendar.require_execution(actor=actor, task_id=task_id)
    except PermissionError:
        if not step.get('assignee_id'):
            raise
        eligibility = calendar.eligibility(
            actor=actor, employee_id=str(step['assignee_id']), task_id=task_id,
            at=datetime.now(timezone.utc), search_days=14)
        next_at = eligibility.get('next_eligible_at')
        return _outcome(step, progressed=False, needs_founder=next_at is None,
                        message=('The assigned worker is unavailable: '
                                 + ', '.join(eligibility['reasons'])
                                 + ('. Work is scheduled for the next allowed window.' if next_at
                                    else '. No allowed slot was found in 14 days; the manager must reschedule.')),
                        schedule_at=next_at)
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


def _test_candidate(actor, repositories, project_id, step) -> dict | None:
    """QA-002: before AI QA, AGO runs a code candidate's tests in isolation.

    Returns None when there is nothing to test (text stage, or already tested).
    """
    router = repositories.resolve(StageProgressionPort)
    stage, task_id = step["stage"], step["task_id"]
    state = router.candidate_test(tenant_id=actor.tenant_id, founder_id=actor.subject,
                                  project_id=project_id, task_id=task_id)
    if not state["required"] or state["status"] not in (None, "started"):
        return None
    tested = router.test_stage_candidate(tenant_id=actor.tenant_id, founder_id=actor.subject,
                                         project_id=project_id, task_id=task_id)
    if tested["status"] == "runner_unavailable":
        # A machine problem, not a defect of the work: wait and try again; it
        # never counts as a failed attempt and never needs a Founder decision.
        return _outcome(step, progressed=False, needs_founder=False,
                        failure_code="test_runner_unavailable",
                        schedule_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                        message="AGO could not run the " + stage + " tests: "
                                + tested["failure_summary"] + " It will try again in 5 minutes.")
    if tested["status"] == "started":
        return _outcome(step, progressed=False, needs_founder=False,
                        message="The " + stage + " tests are already running.")
    return _outcome(step, progressed=True, needs_founder=False,
                    test_status=tested["status"], unittest_cases=tested.get("unittest_cases"),
                    message=tested.get("text") or ("Isolated tests: " + tested["status"]))


def _qa(actor, repositories, project_id, step) -> dict:
    stage = step["stage"]
    if repositories.resolve(StageProgressionPort).qa_attempts(
            tenant_id=actor.tenant_id, task_id=step['task_id']) >= 3:
        return _outcome(step, progressed=False, needs_founder=True,
                        failure_code='qa_attempt_limit',
                        message='Three QA attempts produced no accepted verdict. The QA owner must '
                                'review the evidence; select an independent tester explicitly to resume.')
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
    after = review.get('continuation') or {}
    # What the Founder must decide next (e.g. approve the module plan) is part
    # of the message, not hidden in the continuation details.
    waiting = (" Next, the Founder: " + str(after.get("reason") or "")[:400]
               if after.get('needs_founder') and after.get('reason') else "")
    return _outcome(
        step, progressed=verdict in ("pass", "fail"),
        needs_founder=bool(after.get('needs_founder')),
        qa_verdict=verdict,
        qa_employee_name=review["qa_employee_name"], decision=review.get("continuation"),
        followup=review.get('followup'),
        message=("AI QA by " + review["qa_employee_name"] + ": " + verdict.upper() + " for "
                 + stage + "." + waiting if verdict in ("pass", "fail")
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


def _workspace(actor, repositories, project_id, task_id, changes=None, *, tests=False, terminal=False, stop=None, repair=None):
    allowed(repositories, actor, "approval:founder")
    allowed(repositories, actor, "agent:read")
    if "founder" not in actor.roles:
        raise HTTPException(403, "Founder role required")
    try:
        service = repositories.resolve(StageProgressionPort)
        if tests or terminal:
            if changes is not None:
                allowed(repositories, actor, "agent:dispatch")
                if os.getenv("AGO_ENVIRONMENT", "development") not in ("development", "test", "testing"):
                    raise HTTPException(403, "Local development mode required")
            if terminal:
                return service.workspace_terminal(tenant_id=actor.tenant_id, founder_id=actor.subject,
                    project_id=str(project_id), task_id=str(task_id), request=changes, stop=stop)
            return service.workspace_tests(tenant_id=actor.tenant_id, founder_id=actor.subject,
                                           project_id=str(project_id), task_id=str(task_id),
                                           request=changes)
        return service.development_workspace(
            tenant_id=actor.tenant_id, founder_id=actor.subject, project_id=str(project_id),
            task_id=str(task_id), changes=changes, repair=repair)
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (LookupError, ValueError, PermissionError) as exc:
        translate_error(exc)


@router.get("/projects/{project_id}/tasks/{task_id}/workspace")
def read_workspace(project_id: UUID, task_id: UUID, actor: Principal = Depends(authenticated),
                   repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id)


@router.put("/projects/{project_id}/tasks/{task_id}/workspace")
def save_workspace(project_id: UUID, task_id: UUID, changes: dict,
                   actor: Principal = Depends(authenticated),
                   repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id, changes)


@router.get("/projects/{project_id}/tasks/{task_id}/workspace/tests")
def workspace_history(project_id: UUID, task_id: UUID, actor: Principal = Depends(authenticated),
                      repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id, tests=True)


@router.post("/projects/{project_id}/tasks/{task_id}/workspace/tests")
def test_workspace_revision(project_id: UUID, task_id: UUID, request: dict,
                            actor: Principal = Depends(authenticated),
                            repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id, request, tests=True)


@router.get("/projects/{project_id}/tasks/{task_id}/workspace/terminal")
def terminal_history(project_id: UUID, task_id: UUID, actor: Principal = Depends(authenticated),
                     repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id, terminal=True)


@router.post("/projects/{project_id}/tasks/{task_id}/workspace/terminal")
def run_terminal(project_id: UUID, task_id: UUID, request: dict,
                 actor: Principal = Depends(authenticated),
                 repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id, request, terminal=True)


@router.post("/projects/{project_id}/tasks/{task_id}/workspace/terminal/{attempt_id}/stop")
def stop_terminal(project_id: UUID, task_id: UUID, attempt_id: UUID,
                  actor: Principal = Depends(authenticated),
                  repositories: RepositoryScope = Depends(repository_scope)):
    return _workspace(actor, repositories, project_id, task_id, {}, terminal=True, stop=str(attempt_id))


@router.post("/projects/{project_id}/tasks/{task_id}/workspace/tests/{attempt_id}/repair")
def repair_workspace(project_id: UUID, task_id: UUID, attempt_id: UUID,
                     actor: Principal = Depends(authenticated),
                     repositories: RepositoryScope = Depends(repository_scope)):
    from ago.model_handlers import workspace_repair

    allowed(repositories, actor, "agent:dispatch")
    current = _workspace(actor, repositories, project_id, task_id)
    runs = _workspace(actor, repositories, project_id, task_id, tests=True)["attempts"]
    failed = next((r for r in runs if str(r["attempt_id"]) == str(attempt_id)
                   and r["revision"] == current["revision"]), None)
    if not failed or not failed["receipt"]:
        raise HTTPException(409, "A finished test of the current revision is required")
    try:
        files = workspace_repair(current, failed["receipt"], repositories=repositories,
                                 actor=actor, task_id=task_id, attempt_id=attempt_id)
    except (PermissionError, ValueError) as exc:
        translate_error(exc)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(503, "Local repair inference unavailable") from exc
    revised = _workspace(actor, repositories, project_id, task_id, {
        "run_id": current["run_id"], "expected_revision": current["revision"], "files": files}, repair={
            "provider": "ollama_local", "model": os.environ["AGO_LLM_MODEL"],
            "failed_attempt_id": str(attempt_id), "parent_revision": current["revision"],
            "parent_sha256": current["candidate_sha256"],
        })
    test = {k: revised[k] for k in ("run_id", "revision", "candidate_sha256")}
    test["attempt_id"] = str(uuid4())
    return {"workspace": revised, "test": _workspace(actor, repositories, project_id,
                                                     task_id, test, tests=True)}


@router.post("/projects/{project_id}/tasks/{task_id}/workspace/tests/{attempt_id}/review/{reviewer_id}")
def request_workspace_review(project_id: UUID, task_id: UUID, attempt_id: UUID, reviewer_id: UUID,
                             actor: Principal = Depends(authenticated),
                             repositories: RepositoryScope = Depends(repository_scope)):
    allowed(repositories, actor, "approval:founder")
    try:
        return repositories.resolve(StageProgressionPort).request_workspace_review(
            tenant_id=actor.tenant_id, founder_id=actor.subject, project_id=str(project_id),
            task_id=str(task_id), attempt_id=str(attempt_id), reviewer_id=str(reviewer_id))
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


def _review(repositories, actor, review_id, decision=None):
    allowed(repositories, actor, "qa:review" if decision is not None else "qa:read")
    try:
        return repositories.resolve(StageProgressionPort).workspace_review(
            tenant_id=actor.tenant_id, actor_id=actor.subject, review_id=str(review_id), decision=decision)
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)


@router.get("/workspace-reviews/{review_id}")
def workspace_review_packet(review_id: UUID, actor: Principal = Depends(authenticated),
                            repositories: RepositoryScope = Depends(repository_scope)):
    return _review(repositories, actor, review_id)


@router.post("/workspace-reviews/{review_id}")
def decide_workspace_review(review_id: UUID, decision: dict, actor: Principal = Depends(authenticated),
                            repositories: RepositoryScope = Depends(repository_scope)):
    return _review(repositories, actor, review_id, decision)


@router.post("/workspace-reviews/{review_id}/github-handoff/{github_project_id}/{operation_id}")
def workspace_handoff(review_id: UUID, github_project_id: UUID, operation_id: UUID, request: dict,
                      actor: Principal = Depends(authenticated),
                      repositories: RepositoryScope = Depends(repository_scope)):
    allowed(repositories, actor, "approval:founder")
    if set(request) != {"expected_sha", "message"}:
        raise HTTPException(400, "Expected develop SHA and commit message required")
    try:
        service = repositories.resolve(StageProgressionPort)
        packet = service.workspace_review(tenant_id=actor.tenant_id, actor_id=actor.subject,
                                          review_id=str(review_id))
        project = repositories.resolve(CompanyChatPort).project_details(
            actor.tenant_id, str(packet["project_id"]), reader_id=actor.subject)
        github = repositories.resolve(IntegrationStorePort)
        registered = [row["payload"] for row in github.catalog(actor=actor)["github_projects"]
                      if str(row["payload"]["id"]) == str(github_project_id)]
        if (len(registered) != 1 or registered[0].get("enabled") is not True
                or str(registered[0]["goal_id"]) != str(project["goal_id"])):
            raise PermissionError("GitHub destination must be linked to the reviewed project")
        status = github.github_status(actor=actor, project_id=str(github_project_id))
        if status.get("repository_private") is not True or str(status.get("project_id")) != str(github_project_id):
            raise PermissionError("Private GitHub repository binding required")
        if status.get("develop_sha") != request["expected_sha"]:
            raise RevisionConflict("GitHub develop moved. Reload before preparing a commit.")
        return service.workspace_handoff(
            tenant_id=actor.tenant_id, founder_id=actor.subject, review_id=str(review_id),
            github_project_id=str(github_project_id), operation_id=str(operation_id), **request)
    except RevisionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, PermissionError, LookupError) as exc:
        translate_error(exc)
