"""Founder-approved repair of one existing AGO AI worker -> accountable PM link.

By default READ ONLY. Uses authenticated localhost API, NEVER direct SQL or
original task dispatch. Does not invent employees, change project assignments,
approvals, Board, external GitHub, or AI runtime. Fail-closed on stale state.
"""
from __future__ import annotations

import argparse
import getpass
import json
from uuid import UUID
from urllib.error import HTTPError, URLError

from local_approved_agent_batch import founder_login, local_url
from ago_company_setup import fetch

CONFIRM = "LINK_AGO_WORKER_TO_ACCOUNTABLE_PM"


def uuid(value):
    return str(UUID(str(value)))


def make_preview(report, governance, *, allow_reparent=False):
    """Validate exact current task, PM, worker, and Board before any write."""
    if (not isinstance(report, dict)
            or report.get("kind") != "ago_founder_engineering_preflight_v1"
            or report.get("database_modified") is not False
            or report.get("task_post_authorized") is not False
            or not isinstance(governance, dict)):
        raise PermissionError("Authenticated read-only task and governance evidence required")
    task_id = uuid(report["task_id"])
    if (report.get("task_status") != "waiting_approval"
            or report.get("action_internal_brief") is not True
            or report.get("linked_matching_approval") is not True
            or report.get("founder_discovery_link") is not True
            or report.get("execution_attempted") is not False
            or report.get("blocking_checks") != ["worker_pm_reporting_path_missing"]):
        raise PermissionError("Not the one valid scoped reporting-only repair case")
    link = report.get("reporting_repair_evidence")
    if not isinstance(link, dict):
        raise PermissionError("Reporting identities not available from scoped preflight")
    worker_id, pm_id = uuid(link["worker_id"]), uuid(link["accountable_pm_id"])
    if worker_id == pm_id or link.get("worker_kind") != "ai" or link.get("accountable_pm_kind") != "ai":
        raise PermissionError("Two distinct existing AI PM/worker identities required")
    people = {uuid(e["id"]): e for e in governance.get("employees", [])}
    worker, pm = people.get(worker_id), people.get(pm_id)
    if not worker or not pm or worker.get("kind") != "ai" or pm.get("kind") != "ai":
        raise PermissionError("AGO governance roster does not confirm both AI identities")
    current_manager = (uuid(worker["manager_id"]) if worker.get("manager_id") else None)
    seen_manager = (uuid(link["worker_manager_id"]) if link.get("worker_manager_id") else None)
    if current_manager != seen_manager:
        raise PermissionError("Worker manager changed since database preflight")
    board = [uuid(b["employee_id"]) for b in governance.get("board", [])]
    if len(board) != len(set(board)) or worker_id in board or pm_id in board:
        raise PermissionError("PM and worker must remain distinct from five Board employees")
    if len(board) != 5:
        raise PermissionError("Exactly five distinct appointed Board members required")
    if current_manager == pm_id:
        raise PermissionError("Already directly reporting to PM; refresh server preflight")
    if current_manager and not allow_reparent:
        decision = "requires_explicit_reparent_opt_in"
    else:
        decision = "link_worker_to_existing_pm"
    return {
        "kind": "ago_local_pm_reporting_repair_preview",
        "mode": "read_only",
        "task_id": task_id,
        "worker_id":worker_id,
        "worker_name":worker["name"],
        "accountable_pm_id":pm_id,
        "accountable_pm_name":pm["name"],
        "worker_current_manager_id":current_manager,
        "worker_current_manager_name":link.get("worker_manager_name"),
        "decision":decision,
        "reparent_selected":bool(allow_reparent),
        "database_modified":False,
        "task_executed":False,
        "project_assignment_changed":False,
    }


def apply(request, proposal):
    """One PUT after Founder consent and a fresh, exact GET snapshot check."""
    task_id = uuid(proposal["task_id"])
    path = "/v1/agents/tasks/" + task_id + "/engineering-preflight"
    report = request("GET", path)
    gov = request("GET", "/v1/organization/company/governance")
    fresh = make_preview(report, gov, allow_reparent=proposal["reparent_selected"])
    if fresh != proposal:
        raise PermissionError("Actual PM or worker assignment changed; no write")
    if fresh["decision"] != "link_worker_to_existing_pm":
        raise PermissionError("Existing manager needs explicit --reparent and fresh consent")
    request("PUT", "/v1/organization/company/employees/" + proposal["worker_id"]
            + "/manager", {"manager_id":proposal["accountable_pm_id"]})
    # Never dispatch task, credit model or modify no-replay receipt.
    updated = request("GET", path)
    gov_after = request("GET", "/v1/organization/company/governance")
    employee = next((e for e in gov_after["employees"] if
                     uuid(e["id"]) == proposal["worker_id"]), None)
    actual_manager = (
        uuid(employee["manager_id"]) if employee and employee.get("manager_id") else None
    )
    direct = actual_manager == proposal["accountable_pm_id"]
    return {
        "kind":"ago_local_pm_reporting_repair_result",
        "status":"verified" if direct else "verification_incomplete",
        "worker_id":proposal["worker_id"],
        "accountable_pm_id":proposal["accountable_pm_id"],
        "direct_reporting_verified":direct,
        "preflight_blocking_checks":updated.get("blocking_checks"),
        "seven_role_hierarchy_verified": updated.get("seven_employee_hierarchy_verified") is True,
        "task_post_authorized": False,
        "task_executed": False,
        "original_task_replayed": False,
        "github_modified": False,
        "next_step":"Review this task read-only; future execution needs a separate new approved task",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--reparent", action="store_true",
                        help="Explicitly allow replacement of a NONEMPTY existing worker manager")
    parser.add_argument("--apply", action="store_true",
                        help="Ask exact Founder confirmation for one verified PUT")
    args = parser.parse_args(argv)
    try:
        base, task_id = local_url(args.local_url), uuid(args.task_id)
        tenant=input("AGO organization ID: ").strip()
        email=input("Founder work email: ").strip()
        password=getpass.getpass("Founder password (hidden): ")
        token=founder_login(base,tenant,email,password)
        del password
        req=lambda method,path,body=None:fetch(base,token,method,path,body)
        me=req("GET", "/v1/console/me")
        if ("founder" not in me.get("roles",[])
                or "organization:manage" not in me.get("permissions",[])):
            raise PermissionError("Founder permission required for reporting repair")
        endpoint="/v1/agents/tasks/"+task_id+"/engineering-preflight"
        report=req("GET", endpoint)
        gov=req("GET", "/v1/organization/company/governance")
        preview=make_preview(report,gov,allow_reparent=args.reparent)
        print(json.dumps(preview,indent=2,sort_keys=True))
        if not args.apply:
            return 0
        if preview["decision"] != "link_worker_to_existing_pm":
            raise PermissionError("Current manager is nonempty; preview --reparent first")
        answer=input("Review exact WORKER and PM IDs, then type "+CONFIRM+": ").strip()
        if answer != CONFIRM:
            print(json.dumps({"status":"cancelled","database_modified":False}))
            return 2
        result=apply(req,preview)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0 if result["direct_reporting_verified"] else 2
    except HTTPError as exc:
        print(json.dumps({"status":"stopped_without_retry","error_type":"HTTPError",
                          "http_status":exc.code,"task_replayed":False}))
    except (ValueError,TypeError,RuntimeError,PermissionError,URLError,OSError,
            EOFError,KeyboardInterrupt) as exc:
        print(json.dumps({"status":"stopped_without_retry",
                          "error_type":type(exc).__name__,
                          "task_replayed":False,
                          "next_step":"Inspect current roster and new preflight evidence, never blindly retry"}))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
