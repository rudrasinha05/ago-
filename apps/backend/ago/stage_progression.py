"""PROJ-006: server-side continuation of a Founder project by its AI manager.

The browser used to decide what happens between stages, so a project stopped
whenever no page was open - and stages 2-5 never received a task at all. This
service makes those decisions on the server, in the name of the project's
accountable AI manager:

* the previous stage PASSED independent QA -> open the next stage: add its
  plan step and a PROPOSED governed task for the stage's approved specialist;
* a stage task FAILED (Board stop, invalid code, model timeout) or its QA
  verdict is FAIL -> create the audited recovery / rework task;
* choose the independent AI tester for a stage review.

It never approves, runs, releases or spends: every task it creates is
PROPOSED and goes through the ordinary approval hierarchy. It acts only for
an ACTIVE Founder-approved plan, inside that Founder's signed session, and
only when the accountable manager is an AI employee. Anything it must not
decide (credits, unknown outcomes, missing staff, repeated failures) is
returned as ``needs_founder`` with a plain reason instead of being guessed.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.company_chat import CompanyChat
from ago.organization_store import OrganizationStore
from ago.plan_execution import PlanExecution
from ago.stage_progression_queries import StageProgressionQueries
from ago.task_store import TaskStore

log = logging.getLogger(__name__)

STAGES = ("discovery", "architecture", "implementation", "quality", "release")
QA_ROLE = re.compile(r"\b(qa|quality|test(er|ing)?)\b", re.IGNORECASE)
# The AI manager retries a stage at most this many times; then the Founder decides.
MAX_AI_RECOVERIES = 2
# Run failures a retry can fix. Credit, unstaffed and unknown outcomes are not here.
# worker_timeout is an abandoned run with an UNKNOWN outcome: never retried here.
RETRYABLE_FAILURES = frozenset({
    "engineering_candidate_invalid", "model_timeout", "model_unreachable",
    "model_incomplete",
})
# Steps of ProjectAdvance that the AI manager decides (continue_project).
MANAGER_STEPS = frozenset({"open_stage", "recover"})


def next_step(stages: list[dict]) -> dict:
    """The ONE next step of a project, from its signed stage details.

    Pure decision (the server-side twin of the browser's nextAdvanceStep): the
    first stage in delivery order without a QA PASS decides. It performs
    nothing; every step it names is re-checked by the service that does it.
    """
    ordered = sorted(stages, key=lambda s: int(s["position"]))
    if not ordered:
        return {"step": "unstaffed", "stage": None, "task_id": None}
    for s in ordered:
        if s.get("qa_verdict") == "pass":
            continue
        task_id = str(s["task_id"]) if s.get("task_id") else None
        base = {"stage": s["stage"], "task_id": task_id}
        if task_id is None:
            # A later stage is opened by the AI manager; if it has no staffing
            # the AI CEO fills it or the server names the missing role.
            return {**base, "step": "open_stage" if int(s["position"]) > 1 else "unstaffed"}
        status = s.get("task_status")
        if s.get("qa_verdict") == "fail" or status == "failed":
            return {**base, "step": "recover"}
        if status == "proposed":
            return {**base, "step": "request"}
        if status == "waiting_approval":
            approval = s.get("task_approval_status")
            return {**base, "step": "run" if approval == "approved"
                    else "rejected" if approval == "rejected" else "approve"}
        if status == "running":
            return {**base, "step": "running"}
        if status == "completed" and s.get("agent_run_status") == "completed":
            return {**base, "step": "qa"}
        return {**base, "step": "unknown"}
    return {"step": "done", "stage": None, "task_id": None}


def _board_feedback(result) -> str:
    points = [
        str(v.get("seat")) + ": " + (
            str(v.get("denial_reason") or "").strip()
            or ("gave no clear vote" if v.get("recommendation") == "unverified"
                else "denied without a stated reason"))
        for v in (result.get("board_recommendations") or [])
        if isinstance(v, dict) and v.get("recommendation") != "approve"
    ]
    return "; ".join(points) or "Board did not approve"


class StageProgression:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    # -- public entry points -------------------------------------------------

    @contextmanager
    def advance_guard(self, *, tenant_id: str, project_id: str):
        """Session lock: serialize model/approval work without a long DB transaction.

        A crashed connection releases this lock; recorded task/run state still
        decides whether execution is safe. A lock is never permission to replay.
        """
        key = str(UUID(tenant_id)) + ':' + str(UUID(project_id))
        queries = self.repositories.resolve(StageProgressionQueries)
        acquired = queries.select_project_lock_18((key,)).fetchone()['acquired']
        try:
            yield acquired
        finally:
            if acquired:
                queries.release_project_lock_19((key,))

    def qa_attempts(self, *, tenant_id: str, task_id: str) -> int:
        UUID(tenant_id)
        UUID(task_id)
        return int(self.repositories.resolve(StageProgressionQueries).select_qa_attempts_17(
            (tenant_id, 'ai-qa:' + task_id + ':%')).fetchone()['n'])

    def scheduled_work(self, *, tenant_id: str, project_id: str, task_id: str) -> dict | None:
        for value in (tenant_id, project_id, task_id):
            UUID(value)
        row = self.repositories.resolve(StageProgressionQueries).select_scheduled_followup_16(
            (tenant_id, project_id, task_id)).fetchone()
        return dict(row) if row else None

    def route_followup(self, *, tenant_id: str, founder_id: str, project_id: str,
                       stage: str, code: str, feedback: str, source_task_id: str | None = None,
                       work_task_id: str | None = None, eligible_at: datetime | None = None,
                       owner_kind: str = 'manager', blocked: bool = True) -> dict:
        """Persist a real owner's follow-up and a private Brain signal atomically.

        Called only by governed server operations, never with a client-selected
        owner. Duplicate observation does not create more work or notifications.
        It does not grant permissions or execute the assigned work.
        """
        for value in (tenant_id, founder_id, project_id):
            UUID(value)
        if stage not in STAGES or not re.fullmatch(r'[a-z0-9_]{1,100}', code):
            raise ValueError('Invalid follow-up stage or code')
        queries = self.repositories.resolve(StageProgressionQueries)
        with self.db.transaction():
            context = queries.select_followup_context_10(
                (tenant_id, project_id, founder_id, stage)).fetchone()
            if context is None:
                raise LookupError('Project stage not found')
            source = source_task_id or (str(context['task_id']) if context['task_id'] else None)
            work = work_task_id or (str(context['task_id']) if context['task_id'] else None)
            for task in {source, work} - {None}:
                UUID(task)
                if not queries.select_followup_task_20(
                        (tenant_id, project_id, stage, task, task, task)).fetchone():
                    raise PermissionError('Follow-up task must belong to this project stage')
            people = [dict(p) for p in queries.select_followup_owners_11((tenant_id,)).fetchall()]
            by_id = {str(p['id']): p for p in people}
            manager = by_id.get(str(context['accountable_manager_id']))
            founder = by_id.get(founder_id)
            seat = {'ceo': 'Strategy & Vision', 'technology': 'Technology Oversight',
                    'quality': 'Quality & Release'}.get(owner_kind)
            owner = (by_id.get(str(context['assignee_id'])) if owner_kind == 'worker'
                     else founder if owner_kind == 'founder'
                     else next((p for p in people if p['seat'] == seat and p['kind'] == 'ai'), None)
                     if seat else manager)
            owner = owner or manager or founder
            if owner is None:
                raise PermissionError('No active responsible person is available')
            owner_id = str(owner['id'])
            action = ('Complete the assigned corrective task, address the recorded feedback, '
                      'then submit to independent QA.' if not blocked else
                      'Resolve this blocker within your authority, then resume this project. '
                      'Do not replay unknown work or bypass approvals.')
            if owner_id == founder_id:
                action = 'Review the recorded blocker and authorize the required correction before resuming.'
            if eligible_at is not None:
                if eligible_at.tzinfo is None:
                    raise ValueError('Follow-up schedule requires a timezone')
                action += ' Earliest retry: ' + eligible_at.isoformat() + '; calendar is checked again.'
            status = 'blocked' if blocked else 'scheduled' if eligible_at else 'assigned'
            key = (source or stage) + ':' + code + ':' + owner_id
            if eligible_at:
                key += ':' + eligible_at.isoformat()
            row = queries.insert_followup_12((
                str(uuid4()), tenant_id, project_id, stage, key, source, work,
                owner_id, founder_id, code, (feedback.strip() or code)[:4000], action[:1000],
                status, eligible_at)).fetchone()
            if row is None:
                row = queries.select_followup_13((tenant_id, project_id, stage, key)).fetchone()
            else:
                body = ('Assigned to @' + owner['name'] + ' — ' + context['title'][:220]
                        + ' / ' + stage + '\nFeedback: ' + row['feedback']
                        + '\nNext: ' + action + '\nStatus: ' + status
                        + ('\nWork task: ' + work if work else '')
                        + '\nFollow-up: ' + str(row['id']))
                queries.insert_followup_notice_14((
                    tenant_id, 'employee:' + owner_id, founder_id, body[:6000], owner_id,
                    work, str(uuid5(UUID(project_id), key))))
            return {**dict(row), 'owner_name': owner['name'], 'executed': False}

    def continue_project(
        self, *, tenant_id: str, founder_id: str, project_id: str,
        revise_board_stop: bool = True,
    ) -> dict:
        """Do the ONE pending AI-manager decision for this project, if any.

        Idempotent: calling it again when nothing is pending changes nothing.
        revise_board_stop=False leaves a Board-stopped task linked to its stage,
        so the Founder first sees who denied and why and can still allow it.
        """
        for value in (tenant_id, founder_id, project_id):
            UUID(value)
        queries = self.repositories.resolve(StageProgressionQueries)
        with self.db.transaction():
            project = queries.select_project_01((tenant_id, project_id, founder_id)).fetchone()
            if project is None:
                raise LookupError("Project not found")
            base = {
                "kind": "ago_project_continuation_v1",
                "project_id": project_id,
                "decided_by_employee_id": None,
                "decided_by_name": None,
                "task_approved": False,
                "run_started": False,
            }
            if project["plan_status"] != "active" or project["goal_status"] != "active":
                result = {**base, **self._wait("project_not_active", True,
                                              "The project plan is not approved and active.")}
                result['followup'] = self.route_followup(
                    tenant_id=tenant_id, founder_id=founder_id, project_id=project_id,
                    stage='discovery', code='project_not_active', feedback=result['reason'],
                    owner_kind='founder')
                return result
            manager_id = str(project["accountable_manager_id"])
            staff = {
                str(e["id"]) for e in
                self.repositories.resolve(OrganizationStore).eligible_ai_staff(tenant_id=tenant_id)
            }
            if project["manager_kind"] != "ai" or manager_id not in staff:
                result = {**base, **self._wait(
                    "no_ai_project_manager", True,
                    "The project has no active AI manager; assign one so the work can continue.")}
                result['followup'] = self.route_followup(
                    tenant_id=tenant_id, founder_id=founder_id, project_id=project_id,
                    stage='discovery', code='no_ai_project_manager', feedback=result['reason'],
                    owner_kind='ceo')
                return result
            base["decided_by_employee_id"] = manager_id
            base["decided_by_name"] = project["manager_name"]
            stages = queries.select_stages_02((tenant_id, project_id)).fetchall()
            current = next((s for s in stages if s["qa_verdict"] != "pass"), None)
            for passed in stages:
                if passed['qa_verdict'] == 'pass':
                    queries.resolve_followups_15((tenant_id, project_id, passed['stage']))
            if current is None:
                return {**base, **self._wait("all_stages_passed", False,
                                             "Every stage passed independent QA.")}
            base["stage"] = current["stage"]
            if current["plan_step_id"] is None:
                result = {**base, **self._open_stage(
                    queries, tenant_id=tenant_id, founder_id=founder_id, project=project,
                    stages=stages, current=current, staff=staff)}
            else:
                result = {**base, **self._recover_stage(
                    tenant_id=tenant_id, founder_id=founder_id, project=project,
                    current=current, queries=queries, revise_board_stop=revise_board_stop)}
            if result.get('action') == 'recovered_stage' or result.get('needs_founder') \
                    or result.get('state') == 'board_stopped':
                recovered = result.get('action') == 'recovered_stage'
                code = result.get('recovery_kind') or result['state']
                owner_kind = ('worker' if code == 'qa_rework' else
                              'worker' if code == 'retry' else
                              'founder' if code in ('failure_needs_founder', 'recovery_limit_reached')
                              else 'ceo' if 'staff' in code or 'specialist' in code else 'manager')
                delay = (datetime.now(timezone.utc) + timedelta(seconds=30)
                         if recovered and code == 'retry' else None)
                result['followup'] = self.route_followup(
                    tenant_id=tenant_id, founder_id=founder_id, project_id=project_id,
                    stage=current['stage'], code=code,
                    feedback=(result['reason'] + ('\nQA findings: ' + str(current['qa_evidence'])
                                                  if current['qa_verdict'] == 'fail' else '')),
                    source_task_id=str(current['task_id']) if current['task_id'] else None,
                    work_task_id=result.get('task_id'), owner_kind=owner_kind,
                    blocked=not recovered, eligible_at=delay)
            return result

    def after_task_event(self, *, tenant_id: str, founder_id: str | None, task_id: str) -> dict | None:
        """Called by the server right after a stage task failed or was reviewed.

        Never raises: the triggering run or QA record is already stored, so a
        continuation problem is reported in the result (and the log) instead.
        """
        row = None
        try:
            with self.db.transaction():
                row = self.repositories.resolve(StageProgressionQueries).select_project_of_task_08(
                    (tenant_id, task_id, founder_id, founder_id)).fetchone()
                if row is None:
                    return None
                # A Board denial is shown to the Founder before it is revised:
                # the revision happens on the next explicit continue.
                return self.continue_project(
                    tenant_id=tenant_id, founder_id=str(row["founder_id"]),
                    project_id=str(row["project_id"]), revise_board_stop=False)
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            log.warning("AGO stage continuation did not complete: %s", type(exc).__name__)
            result = {
                "kind": "ago_project_continuation_v1", "action": "error",
                "needs_founder": True, "state": "continuation_error",
                "reason": "The automatic next step could not be recorded ("
                          + type(exc).__name__ + "). Press Advance to try it again.",
                "task_approved": False, "run_started": False,
            }
            if row:
                try:
                    result['followup'] = self.route_followup(
                        tenant_id=tenant_id, founder_id=str(row['founder_id']),
                        project_id=str(row['project_id']), stage=row['stage'],
                        source_task_id=task_id, code='continuation_error', owner_kind='manager',
                        feedback=result['reason'])
                except Exception:  # noqa: BLE001 - do not misreport the already recorded run
                    result['followup_recorded'] = False
                    log.warning('AGO continuation follow-up could not be persisted')
            return result

    def pick_qa_reviewer(self, *, tenant_id: str, project_id: str, excluded: set[str]) -> dict:
        """The independent AI tester for a stage review.

        Prefers the project's approved quality-stage tester; never returns an
        employee who helped build the work under review.
        """
        UUID(tenant_id)
        UUID(project_id)
        rows = self.repositories.resolve(StageProgressionQueries).select_qa_candidates_09(
            (project_id, tenant_id)).fetchall()
        for row in rows:
            if str(row["id"]) not in excluded and QA_ROLE.search(row["role_title"] or ""):
                return dict(row)
        raise PermissionError(
            "No independent AI tester is available: hire or retitle an AI employee as "
            "QA Engineer who did not build this work")

    # -- decisions -----------------------------------------------------------

    @staticmethod
    def _wait(state: str, needs_founder: bool, reason: str) -> dict:
        return {"action": "none", "state": state, "needs_founder": needs_founder, "reason": reason}

    def _open_stage(self, queries, *, tenant_id, founder_id, project, stages, current, staff):
        previous = next((s for s in stages if s["position"] == current["position"] - 1), None)
        if previous is None or previous["plan_step_id"] is None:
            return self._wait("first_stage_unstaffed", True,
                              "The first stage has no AI worker; staff it first.")
        # 'current' is the first stage without a PASS, so 'previous' passed QA.
        stage = current["stage"]
        assignee = (str(current["approved_assignee_id"])
                    if current["approved_assignee_id"] else None)
        staffed_by = None
        if assignee is None:
            # Founder rule: unassigned roles are filled by the AI leadership from
            # existing employees. The AI CEO does that here; with nobody suitable
            # the Founder gets the exact missing role instead of a silent stop.
            try:
                filled = self.repositories.resolve(CompanyChat).ceo_fill_stage(
                    tenant_id=tenant_id, founder_id=founder_id,
                    project_id=str(project["id"]), stage=stage)
            except PermissionError as exc:
                return self._wait("stage_not_staffed", True, str(exc))
            assignee, staffed_by = filled["assignee_id"], filled["ceo_name"]
            current = {**current, "approved_assignee_id": assignee,
                       "approved_assignee_name": filled["assignee_name"]}
        if assignee not in staff:
            return self._wait(
                "stage_specialist_unavailable", True,
                "The approved " + stage + " specialist is no longer an active AI employee.")
        manager_id = str(project["accountable_manager_id"])
        by_stage = {s["stage"]: s for s in stages}
        other = {"quality": "implementation", "implementation": "quality"}.get(stage)
        other_worker = by_stage.get(other, {}).get("approved_assignee_id") if other else None
        if (stage == "quality" and assignee == manager_id) or (
                other_worker is not None and str(other_worker) == assignee):
            return self._wait(
                "tester_not_independent", True,
                "Implementation and QA need different AI specialists, and the tester "
                "must not be the project manager.")
        step_id = str(uuid4())
        queries.insert_stage_step_03((
            step_id, tenant_id, str(project["plan_id"]), current["position"], assignee,
            str(previous["plan_step_id"]),
        ))
        task = self.repositories.resolve(TaskStore).propose(
            tenant_id=tenant_id, action="internal:brief", assignee_id=assignee)
        if queries.link_step_task_04((task.id, tenant_id, step_id)).rowcount != 1:
            raise ValueError("Stage step changed while it was being opened")
        if queries.link_stage_step_05((step_id, tenant_id, str(project["id"]), stage)).rowcount != 1:
            raise ValueError("Stage was opened by another request")
        record = queries.insert_progression_06((
            tenant_id, str(project["id"]), str(project["plan_id"]), previous["stage"], stage,
            str(previous["task_id"]), step_id, task.id, assignee, manager_id, founder_id,
        )).fetchone()
        queries.insert_project_notice_07((
            tenant_id, founder_id, project["manager_name"] + " (AI project manager)",
            previous["stage"].capitalize() + " passed independent QA. I opened the " + stage
            + " stage and assigned its task to " + str(current["approved_assignee_name"])
            + ". The task is proposed; it still needs approval before any work runs.",
            assignee,
        ))
        return {
            "action": "opened_stage", "state": "task_proposed", "needs_founder": False,
            "reason": previous["stage"] + " passed QA",
            "from_stage": previous["stage"], "task_id": task.id, "plan_step_id": step_id,
            "assignee_id": assignee, "assignee_name": current["approved_assignee_name"],
            "staffed_by_ceo": staffed_by,
            "progression_id": int(record["id"]),
            "recorded_at": record["created_at"].isoformat(),
        }

    def _recover_stage(self, *, tenant_id, founder_id, project, current, queries,
                       revise_board_stop):
        stage, status = current["stage"], current["task_status"]
        if current["task_id"] is None:
            return self._wait("stage_task_missing", True,
                              "The " + stage + " stage has a plan step but no task yet.")
        result = current["run_result"] if isinstance(current["run_result"], dict) else {}
        if status == "completed" and current["qa_verdict"] == "fail":
            kind = "qa_rework"
            reason = ("QA rework: " + str(current.get('qa_evidence') or
                       "Independent QA failed; inspect the original review before retrying"))[:500]
        elif status == "failed" and current["run_status"] != "running":
            if current["run_status"] == "completed" and result.get("board_blocked") is True:
                kind = "board_revision"
                reason = "Revise to fix Board feedback: " + _board_feedback(result)
                if not revise_board_stop:
                    return self._wait(
                        "board_stopped", False,
                        "The Board stopped the " + stage + " stage ("
                        + str(result.get("blocked_by_board_seat") or "a Board seat")
                        + "): " + _board_feedback(result)[:500]
                        + ". The denial stays on the stage for the Founder to read; on the "
                        "next advance the AI manager revises the proposal and resubmits it.")
            elif current["failure_code"] in RETRYABLE_FAILURES:
                kind = "retry"
                reason = "Retry after run failure: " + str(current["failure_code"])
            else:
                return self._wait(
                    "failure_needs_founder", True,
                    "The " + stage + " task failed (" + str(current["failure_code"] or "unknown")
                    + "). The AI manager must not retry this kind of failure; the Founder decides.")
        else:
            return self._wait(
                "stage_in_progress", False,
                "The " + stage + " task is " + str(status)
                + ("" if current["qa_verdict"] else "; no QA verdict yet") + ".")
        if int(current["ai_recoveries"] or 0) >= MAX_AI_RECOVERIES:
            return self._wait(
                "recovery_limit_reached", True,
                "The AI manager already retried the " + stage + " stage "
                + str(MAX_AI_RECOVERIES) + " times. The Founder decides what happens next.")
        active = {str(e['id']) for e in self.repositories.resolve(OrganizationStore).eligible_ai_staff(
            tenant_id=tenant_id)}
        if str(current['approved_assignee_id']) not in active:
            return self._wait('stage_specialist_unavailable', True,
                              'The responsible worker is unavailable; leadership must review a replacement.')
        manager_id = str(project["accountable_manager_id"])
        recovery = self.repositories.resolve(PlanExecution).recover_failed_stage(
            tenant_id=tenant_id, founder_id=founder_id, project_id=str(project["id"]),
            stage=stage, failed_task_id=str(current["task_id"]), reason=reason[:500],
            decided_by_employee_id=manager_id,
        )
        attempt = int(current["ai_recoveries"] or 0) + 1
        queries.insert_project_notice_07((
            tenant_id, founder_id, project["manager_name"] + " (AI project manager)",
            {"qa_rework": "The independent tester failed the " + stage + " stage.",
             "board_revision": "The Board stopped the " + stage + " stage.",
             "retry": "The " + stage + " task failed (" + str(current["failure_code"]) + ")."}[kind]
            + " I created a new task for it (automatic attempt " + str(attempt) + " of "
            + str(MAX_AI_RECOVERIES) + "). The old task stays as evidence; the new one "
            "still needs approval before any work runs.",
            None,
        ))
        return {
            "action": "recovered_stage", "state": "task_proposed", "needs_founder": False,
            "reason": reason[:500], "recovery_kind": kind,
            "failed_task_id": str(current["task_id"]),
            "task_id": recovery["recovery_task_id"],
            "recovery_id": recovery["recovery_id"],
            "ai_recovery_attempt": attempt, "ai_recovery_limit": MAX_AI_RECOVERIES,
        }
