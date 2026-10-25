"""Read-only, founder-scoped diagnosis of local seven-role engineering gates.

This inspects preconditions and recent run history only. It never dispatches,
approves, consumes credits, starts a local model, records events or changes DB.
The mutable calendar/constitutional execution checks remain separate gates.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from ago.agent_runtime_queries import AgentRuntimeQueries
from ago.backend_contracts import RepositoryScope
from ago.company_ollama_chain_queries import CompanyOllamaChainQueries

BLOCKER_CODES = {
    "Approved founder project discovery task required": "project_discovery_link_missing",
    "Founder-owned ACTIVE plan and linked discovery task required":
        "founder_project_not_active_or_discovery_link_missing",
    "Engineering generation needs five real reviewed Board seats":
        "five_board_review_not_configured",
    "Five-seat local Board review is not enabled outside local development":
        "local_environment_not_allowed",
    "Founder must appoint all required real AI Board seats":
        "board_appointments_incomplete",
    "Real accountable PM and discovery assignee required":
        "pm_or_discovery_employee_missing",
    "Full Board execution requires actual employee-to-PM reporting hierarchy":
        "worker_pm_reporting_path_missing",
    "Board, PM and worker must be actual AI employees":
        "board_pm_or_worker_not_ai",
    "All Board, PM and worker roles need distinct employees":
        "board_pm_worker_identities_not_distinct",
}


def inspect_engineering_task(db, *, tenant_id: str, founder_id: str,
                             task_id: str, set_read_only: bool = False) -> dict:
    """Return only safe statuses; never expose project briefs or source drafts."""
    for value in (tenant_id, founder_id, task_id):
        UUID(str(value))
    if set_read_only:
        # Called inside a transaction opened by the founder-only GET endpoint.
        db.execute("SET TRANSACTION READ ONLY")
    repositories = RepositoryScope(db)
    report = {
        "kind": "ago_founder_engineering_preflight_v1",
        "task_id": str(task_id),
        "mode": "read_only",
        "database_modified": False,
        "task_exists": False,
        "task_status": None,
        "action_internal_brief": False,
        "linked_matching_approval": False,
        "task_approval_status": None,
        "founder_discovery_link": False,
        "seven_employee_hierarchy_verified": False,
        "assigned_role_names": [],
        "blocking_checks": [],
        "latest_run_status": None,
        "latest_run_failure_code": None,
        "execution_attempted": False,
        "unverified_execution_gates": [
            "calendar_at_dispatch_time", "constitutional_permission_at_dispatch",
            "task_execute_grant", "employee_behavior_review",
            "virtual_credit_budget", "local_ollama_response",
        ],
        "task_post_authorized": False,
        # Only populated after a specific real hierarchy failure, not globally.
        "reporting_repair_evidence": None,
    }
    task = db.execute(
        """SELECT t.action,t.status,t.approval_id,t.assignee_id
           FROM ago_governed_tasks t
           WHERE t.tenant_id=%s AND t.id=%s""",
        (tenant_id, task_id),
    ).fetchone()
    if not task:
        report["blocking_checks"].append("task_not_found_for_founder_tenant")
        return report
    report["task_exists"] = True
    if task["status"] in ("proposed", "waiting_approval", "running", "failed", "completed"):
        report["task_status"] = task["status"]
    report["action_internal_brief"] = task["action"] == "internal:brief"
    if not report["action_internal_brief"]:
        report["blocking_checks"].append("task_action_not_internal_brief")
    if task["status"] != "waiting_approval":
        report["blocking_checks"].append("task_not_awaiting_approved_dispatch")
    approval = None
    if task["approval_id"]:
        approval = db.execute(
            """SELECT action,status FROM ago_approval_requests
               WHERE tenant_id=%s AND id=%s""",
            (tenant_id, task["approval_id"]),
        ).fetchone()
    if approval:
        if approval["status"] in ("pending", "approved", "denied"):
            report["task_approval_status"] = approval["status"]
        report["linked_matching_approval"] = (
            approval["action"] == task["action"] and approval["status"] == "approved"
        )
    if not report["linked_matching_approval"]:
        report["blocking_checks"].append("matching_approval_not_approved")
    context = repositories.resolve(AgentRuntimeQueries).select_ago_founder_project_12(
        (task_id, tenant_id),
    ).fetchone()
    report["founder_discovery_link"] = context is not None
    if context is None:
        report["blocking_checks"].append("founder_discovery_link_missing")
    elif report["action_internal_brief"]:
        try:
            participants = repositories.resolve(CompanyOllamaChainQueries).assignments(
                tenant_id=tenant_id, actor_id=founder_id,
                task=SimpleNamespace(
                    id=task_id,
                    project_context={"intake_id": str(context["id"])},
                ),
            )
            report["seven_employee_hierarchy_verified"] = (
                len(participants) == 7
                and len({p["employee_id"] for p in participants}) == 7
            )
            if report["seven_employee_hierarchy_verified"]:
                report["assigned_role_names"] = [p["role"] for p in participants]
            else:
                report["blocking_checks"].append("seven_distinct_ai_employees_required")
        except PermissionError as exc:
            failure_code = BLOCKER_CODES.get(str(exc), "company_hierarchy_not_verified")
            report["blocking_checks"].append(failure_code)
            if failure_code == "worker_pm_reporting_path_missing":
                # Scope matches the already checked ACTIVE founder-owned
                # discovery step. Return only AI identity and current manager,
                # never project brief or task payload. SQL read-only transaction.
                link = db.execute("""
                    SELECT w.id AS worker_id, w.name AS worker_name,
                           w.kind AS worker_kind,
                           w.manager_id AS worker_manager_id,
                           mgr.name AS worker_manager_name,
                           pm.id AS pm_id, pm.name AS pm_name,
                           pm.kind AS pm_kind
                    FROM ago_founder_intakes i
                    JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id
                      AND p.id=i.plan_id AND p.status='active'
                    JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
                      AND l.intake_id=i.id
                    JOIN ago_founder_intake_stages st ON st.tenant_id=i.tenant_id
                      AND st.intake_id=i.id AND st.stage='discovery'
                    JOIN ago_plan_steps ps ON ps.tenant_id=st.tenant_id
                      AND ps.id=st.plan_step_id AND ps.plan_id=i.plan_id
                    JOIN ago_governed_tasks t ON t.tenant_id=i.tenant_id
                      AND t.id=ps.task_id AND t.action='internal:brief'
                    JOIN ago_employees w ON w.tenant_id=t.tenant_id
                      AND w.id=t.assignee_id
                    JOIN ago_employees pm ON pm.tenant_id=i.tenant_id
                      AND pm.id=l.accountable_manager_id
                    LEFT JOIN ago_employees mgr ON mgr.tenant_id=w.tenant_id
                      AND mgr.id=w.manager_id
                    WHERE i.tenant_id=%s AND i.founder_id=%s
                      AND i.id=%s AND t.id=%s
                    LIMIT 1
                """, (tenant_id, founder_id, context["id"], task_id)).fetchone()
                if link:
                    report["reporting_repair_evidence"] = {
                        "worker_id": str(link["worker_id"]),
                        "worker_name": link["worker_name"],
                        "worker_kind": link["worker_kind"],
                        "worker_manager_id": (
                            str(link["worker_manager_id"])
                            if link["worker_manager_id"] else None
                        ),
                        "worker_manager_name": link["worker_manager_name"],
                        "accountable_pm_id": str(link["pm_id"]),
                        "accountable_pm_name": link["pm_name"],
                        "accountable_pm_kind": link["pm_kind"],
                        "direct_link_required": True,
                    }
    latest = db.execute(
        """SELECT status,failure_code FROM ago_agent_runs
           WHERE tenant_id=%s AND task_id=%s
           ORDER BY started_at DESC,id LIMIT 1""",
        (tenant_id, task_id),
    ).fetchone()
    if latest:
        report["execution_attempted"] = True
        report["latest_run_status"] = (
            latest["status"] if latest["status"] in
            ("running", "completed", "failed") else None
        )
        report["latest_run_failure_code"] = (
            latest["failure_code"] if latest["failure_code"] in
            ("handler_error", "worker_timeout") else None
        )
        report["blocking_checks"].append("prior_run_found_do_not_replay")
    report["blocking_checks"] = list(dict.fromkeys(report["blocking_checks"]))
    report["checked_preconditions_pass"] = not report["blocking_checks"]
    # A GET diagnostic never authorizes a POST, even when checked conditions pass.
    return report
