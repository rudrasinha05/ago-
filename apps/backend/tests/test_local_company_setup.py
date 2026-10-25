"""No-write and idempotency tests for the Founder-only local role planner."""
import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest

SCRIPT=Path(__file__).resolve().parents[3]/"scripts"/"ago_company_setup.py"
sys.path.insert(0,str(SCRIPT.parent))
loader=importlib.util.spec_from_file_location("ago_company_setup",SCRIPT)
setup=importlib.util.module_from_spec(loader)
loader.loader.exec_module(setup)


def empty():
    return [],{"employees":[],"board":[]}


def test_core_plan_has_five_distinct_real_board_seats_and_complete_duties():
    p=setup.plan(*empty(),create_missing=True)
    assert [x["code"] for x in p["roles"]]==["CEO","CTO","CFO","CISO","CQO"]
    assert len({x["board_seat"] for x in p["roles"]})==5
    assert all(len(x["responsibilities"])>50 for x in p["roles"])
    assert p["new_ai_records"]==5 and not p["database_modified"]


def test_full_scope_offers_seven_more_roles_without_new_board_seats():
    p=setup.plan(*empty(),scope="full",create_missing=True)
    assert len(p["roles"])==12
    assert len([x for x in p["roles"] if x["board_seat"]])==5
    assert len({x["code"] for x in p["roles"]})==12


def test_empty_default_plan_refuses_implicit_employee_creation():
    p=setup.plan(*empty())
    assert p["new_ai_records"]==0 and len(p["vacant"])==5


def test_existing_appointed_ai_reused_and_human_rejected():
    key=str(uuid4())
    roster={"employees":[{"id":key,"kind":"ai","name":"CEO",
                           "role_title":"Chief Executive Officer (CEO)"}],
            "board":[{"seat":"Strategy & Vision","employee_id":key}]}
    p=setup.plan([],roster,create_missing=True)
    assert p["roles"][0]["action"]=="appointed"
    assert p["roles"][0]["employee_id"]==key
    roster["employees"][0]["kind"]="human"
    with pytest.raises(PermissionError):
        setup.plan([],roster,create_missing=True)


def test_duplicate_ai_board_identity_fails_closed():
    key=str(uuid4())
    roster={"employees":[{"id":key,"kind":"ai","name":"AI"}],
            "board":[{"seat":"Strategy & Vision","employee_id":key},
                     {"seat":"Technology Oversight","employee_id":key}]}
    with pytest.raises(PermissionError):
        setup.plan([],roster,create_missing=True)


def test_unknown_manual_assignment_fails_closed():
    with pytest.raises(ValueError):
        setup.plan(*empty(),mapping={"FOUNDER":str(uuid4())})
    with pytest.raises(PermissionError):
        setup.plan(*empty(),mapping={"CEO":str(uuid4())},create_missing=True)


def test_apply_creates_five_ai_roles_then_readback_verifies_without_task_run():
    departments=[]
    workforce={"employees":[],"board":[]}
    calls=[]
    def request(method,path,body=None):
        calls.append((method,path))
        if method=="GET" and path.endswith("/departments"):
            return list(departments)
        if method=="GET" and path.endswith("/governance"):
            return {"employees":[dict(e) for e in workforce["employees"]],
                    "board":[dict(e) for e in workforce["board"]]}
        if method=="POST" and path.endswith("/departments"):
            entry={"id":str(uuid4()),"name":body["name"]}
            departments.append(entry)
            return entry
        if method=="POST" and path.endswith("/employees"):
            entry={"id":str(uuid4()),"name":body["name"],"kind":"ai",
                   "manager_id":None,"role_title":None}
            workforce["employees"].append(entry)
            return entry
        if method=="PUT" and path.endswith("/role"):
            for item in workforce["employees"]:
                if item["id"]==path.split("/")[-2]:
                    item.update(body)
                    return body
        if method=="PUT" and path.endswith("/manager"):
            for item in workforce["employees"]:
                if item["id"]==path.split("/")[-2]:
                    item.update(body)
                    return body
        if method=="POST" and path.endswith("/board/appoint"):
            workforce["board"].append(body)
            return body
        raise AssertionError("Unexpected API path: "+path)
    proposal=setup.plan(*empty(),create_missing=True)
    result=setup.apply(request,proposal)
    assert result["board_verified"] is True
    assert len(workforce["employees"])==5
    assert len(workforce["board"])==5
    assert result["tasks_executed"]==0
    assert not any("/tasks/" in path or path.endswith("/run") for _,path in calls)
