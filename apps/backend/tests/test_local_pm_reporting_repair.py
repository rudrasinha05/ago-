"""Read-only and founder-confirmed worker -> accountable PM repair tests."""
import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest

SCRIPT=Path(__file__).resolve().parents[3]/"scripts"/"ago_pm_reporting_repair.py"
sys.path.insert(0,str(SCRIPT.parent))
spec=importlib.util.spec_from_file_location("ago_pm_reporting_repair",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixtures(manager=None):
    task, worker, pm = (str(uuid4()) for _ in range(3))
    seats = [str(uuid4()) for _ in range(5)]
    report={
        "kind":"ago_founder_engineering_preflight_v1",
        "task_id":task, "task_status":"waiting_approval",
        "action_internal_brief":True,"linked_matching_approval":True,
        "founder_discovery_link":True,"execution_attempted":False,
        "blocking_checks":["worker_pm_reporting_path_missing"],
        "database_modified":False,"task_post_authorized":False,
        "reporting_repair_evidence":{
            "worker_id":worker,"worker_name":"Engineer",
            "worker_kind":"ai","worker_manager_id":manager,
            "worker_manager_name":"Original Boss" if manager else None,
            "accountable_pm_id":pm,"accountable_pm_name":"Project Manager",
            "accountable_pm_kind":"ai",
        },
    }
    governance={
        "employees":[{"id":worker,"name":"Engineer","kind":"ai","manager_id":manager},
                     {"id":pm,"name":"PM","kind":"ai","manager_id":None}],
        "board":[{"seat":str(i),"employee_id":s} for i,s in enumerate(seats)],
    }
    return report,governance


def test_one_missing_link_is_planned_without_writing():
    report,gov=fixtures()
    p=mod.make_preview(report,gov)
    assert p["decision"]=="link_worker_to_existing_pm"
    assert p["database_modified"] is False
    assert p["worker_id"] != p["accountable_pm_id"]


def test_nonempty_manager_never_silently_reparented():
    manager=str(uuid4())
    report,gov=fixtures(manager)
    p=mod.make_preview(report,gov)
    assert p["decision"]=="requires_explicit_reparent_opt_in"
    p2=mod.make_preview(report,gov,allow_reparent=True)
    assert p2["decision"]=="link_worker_to_existing_pm"
    assert p2["worker_current_manager_id"]==manager


def test_fake_or_divergent_identity_blocks():
    report,gov=fixtures()
    gov["employees"][0]["kind"]="human"
    report["reporting_repair_evidence"]["worker_kind"]="human"
    preview=mod.make_preview(report,gov)
    assert preview["decision"]=="blocked_invalid_project_staffing"
    assert "task_worker_is_not_ai" in preview["identity_blockers"]
    gov["employees"][0]["kind"]="ai"
    report["reporting_repair_evidence"]["worker_kind"]="ai"
    report["reporting_repair_evidence"]["worker_manager_id"]=str(uuid4())
    with pytest.raises(PermissionError):
        mod.make_preview(report,gov)


def test_no_forged_board_or_pm_identity():
    report,gov=fixtures()
    gov["board"][0]["employee_id"]=report["reporting_repair_evidence"]["worker_id"]
    preview=mod.make_preview(report,gov)
    assert preview["decision"]=="blocked_invalid_project_staffing"
    assert "project_pm_or_worker_also_holds_board_seat" in preview["identity_blockers"]


def test_unapproved_task_no_repair():
    report,gov=fixtures()
    report["linked_matching_approval"]=False
    with pytest.raises(PermissionError):
        mod.make_preview(report,gov)


def test_one_confirmed_put_and_actual_readback_never_dispatch():
    report,gov=fixtures()
    proposal=mod.make_preview(report,gov)
    calls=[]
    def request(method,path,body=None):
        calls.append((method,path,body))
        if method=="GET" and path.endswith("/engineering-preflight"):
            return report if len([x for x in calls if x[1].endswith("engineering-preflight")])==1 else {
                **report,
                "seven_employee_hierarchy_verified": True,
                "blocking_checks": [],
            }
        if method=="GET" and path.endswith("/governance"):
            return gov
        if method=="PUT" and path.endswith("/manager"):
            gov["employees"][0]["manager_id"]=body["manager_id"]
            return {"id":proposal["worker_id"],"manager_id":body["manager_id"]}
        raise AssertionError("Unexpected action "+path)
    result=mod.apply(request,proposal)
    assert result["status"]=="verified"
    assert result["seven_role_hierarchy_verified"] is True
    assert len([x for x in calls if x[0]=="PUT"])==1
    assert all("/run" not in x[1] for x in calls)


def test_failure_summary_reports_safe_stage_not_password_or_project():
    from urllib.error import HTTPError
    unauthorized=HTTPError("http://localhost:8000/private",401,"SECRET",{},None)
    # HTTPError uses numeric status in actual requests.
    unauthorized.code=401
    report=mod.failure_summary(unauthorized,"founder_login")
    assert report["reason_code"]=="credentials_rejected_or_invalid"
    assert report["failure_stage"]=="founder_login"
    assert "SECRET" not in str(report) and "/private" not in str(report)
    missing=mod.failure_summary(
        PermissionError("Reporting identities not available from scoped preflight"),
        "validate_pm_worker_preview",
    )
    assert missing["reason_code"]=="backend_missing_reporting_repair_evidence_restart_updated_server"
    assert missing["task_replayed"] is False
    assert missing["database_modified_by_this_preview"] is False
    assert missing["write_may_have_been_attempted"] is False
    custom=mod.failure_summary(
        PermissionError("Private founder project details should never print"),
        "validate_pm_worker_preview",
    )
    assert "Private founder project" not in str(custom)

def test_human_founder_project_leader_is_truthfully_reported_read_only():
    report,gov=fixtures()
    gov["employees"][1]["kind"]="human"
    report["reporting_repair_evidence"]["accountable_pm_kind"]="human"
    result=mod.make_preview(report,gov)
    assert result["decision"]=="blocked_invalid_project_staffing"
    assert result["accountable_pm_kind"]=="human"
    assert "accountable_project_leader_is_not_ai" in result["identity_blockers"]
    assert result["database_modified"] is False


def test_same_worker_is_project_leader_cannot_be_reparented():
    report,gov=fixtures()
    worker=report["reporting_repair_evidence"]["worker_id"]
    report["reporting_repair_evidence"]["accountable_pm_id"]=worker
    report["reporting_repair_evidence"]["accountable_pm_name"]="Engineer"
    report["reporting_repair_evidence"]["accountable_pm_kind"]="ai"
    gov["employees"][1]["id"]=worker
    result=mod.make_preview(report,gov,allow_reparent=True)
    assert result["decision"]=="blocked_invalid_project_staffing"
    assert "worker_and_project_leader_are_same_employee" in result["identity_blockers"]


def test_blocked_invalid_project_leader_cannot_mutate():
    report,gov=fixtures()
    gov["employees"][1]["kind"]="human"
    report["reporting_repair_evidence"]["accountable_pm_kind"]="human"
    proposal=mod.make_preview(report,gov)
    observed=[]
    def req(method,path,body=None):
        observed.append((method,path))
        if method=="GET" and path.endswith("engineering-preflight"):
            return report
        if method=="GET" and path.endswith("governance"):
            return gov
        raise AssertionError("Blocked repair attempted a write")
    with pytest.raises(PermissionError):
        mod.apply(req,proposal)
    assert all(method=="GET" for method,_ in observed)
