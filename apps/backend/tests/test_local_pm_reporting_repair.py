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
    with pytest.raises(PermissionError):
        mod.make_preview(report,gov)
    gov["employees"][0]["kind"]="ai"
    report["reporting_repair_evidence"]["worker_manager_id"]=str(uuid4())
    with pytest.raises(PermissionError):
        mod.make_preview(report,gov)


def test_no_forged_board_or_pm_identity():
    report,gov=fixtures()
    gov["board"][0]["employee_id"]=report["reporting_repair_evidence"]["worker_id"]
    with pytest.raises(PermissionError):
        mod.make_preview(report,gov)


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
