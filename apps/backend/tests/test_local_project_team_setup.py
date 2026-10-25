"""Dedicated AI PM and discovery employee remain distinct from five Board identities."""
import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest

path=Path(__file__).resolve().parents[3]/"scripts"/"ago_project_team_setup.py"
sys.path.insert(0,str(path.parent))
spec=importlib.util.spec_from_file_location("ago_project_team_setup",path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample():
    dep=str(uuid4())
    board=[{"seat":"Strategy & Vision","employee_id":str(uuid4())}]
    for seat in ("Technology Oversight","Finance & Budget","Risk & Compliance",
                 "Quality & Release"):
        board.append({"seat":seat,"employee_id":str(uuid4())})
    people=[{"id":board[0]["employee_id"],"name":"AGO AI CEO",
             "kind":"ai","department_id":dep,"manager_id":None}]
    return [{"id":dep,"name":"AGO AI Leadership"}],{"board":board,"employees":people}


def test_empty_board_is_never_silently_created():
    ds,gov=sample()
    gov["board"]=[]
    with pytest.raises(PermissionError):
        mod.preview(ds,gov,create_missing=True)


def test_readonly_preview_creates_only_project_pm_and_worker_not_board():
    ds,gov=sample()
    p=mod.preview(ds,gov,create_missing=True)
    assert [x["name"] for x in p["roles"]]==[
        "AGO AI Project Manager","AGO AI Discovery Analyst",
    ]
    assert p["new_ai_employees"]==2
    assert p["board_unchanged"]
    assert p["database_modified"] is False
    assert p["tasks_executed"]==0


def test_preexisting_manager_conflict_is_refused():
    ds,gov=sample()
    gov["employees"].append({
        "id":str(uuid4()),"name":"AGO AI Project Manager",
        "kind":"ai","manager_id":str(uuid4()),"department_id":ds[0]["id"],
    })
    with pytest.raises(PermissionError):
        mod.preview(ds,gov,create_missing=True)


def test_apply_creates_exact_two_distinct_ai_employees_and_readback_verifies():
    ds,gov=sample()
    calls=[]
    def api(method,path,body=None):
        calls.append((method,path,body))
        if method=="GET" and path.endswith("/departments"):
            return ds
        if method=="GET" and path.endswith("/governance"):
            return gov
        if method=="POST" and path.endswith("/employees"):
            emp={**body,"id":str(uuid4()),"role_title":""}
            gov["employees"].append(emp)
            return emp
        if method=="PUT" and path.endswith("/role"):
            for e in gov["employees"]:
                if e["id"]==path.split("/")[-2]:
                    e.update(body)
                    return body
        raise AssertionError("Unexpected API: "+path)
    proposal=mod.preview(ds,gov,create_missing=True)
    result=mod.apply(api,proposal)
    assert result["verified"] is True
    assert result["existing_project_leads_modified"] is False
    assert result["tasks_executed"]==0
    assert len([c for c in calls if c[0]=="POST"])==2
    assert not any("/tasks/" in c[1] or "/run" in c[1] for c in calls)
