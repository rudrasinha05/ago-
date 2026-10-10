"""Section 21: real PostgreSQL HR lifecycle cannot impersonate human reviews."""
from uuid import uuid4

import pytest

from test_m7_http_postgres import case as case, decide, post


def _change(client, founder, reviewer, change_kind, target_id, **extra):
    url = "/v1/operations/enterprise/organization"
    request = post(client, url + "/approval", founder,
                   {"change_kind": change_kind, "target_id": target_id})
    payload = {"change_kind": change_kind, "target_id": target_id,
               "approval_id": request["approval_id"],
               "reason": "Reviewed operational organizational adjustment", **extra}
    post(client, url + "/apply", founder, payload, expected=403)
    decide(client, reviewer, request["approval_id"])
    result = post(client, url + "/apply", founder, payload)
    assert result["independently_approved"] and not result["idempotent"]
    assert post(client, url + "/apply", founder, payload)["idempotent"] is True
    return result


def test_human_review_required_for_department_and_employee_lifecycle(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = str(uuid4())
    assert _change(client, founder, reviewer, "created", dept,
                   name="Independently Reviewed Department")["change_kind"] == "created"
    agent = str(uuid4())
    assert _change(client, founder, reviewer, "hired", agent,
                   department_id=dept, name="Approved AI Employee")["change_kind"] == "hired"
    assert _change(client, founder, reviewer, "promoted", agent,
                   role_level=2)["change_kind"] == "promoted"
    assert _change(client, founder, reviewer, "terminated", agent)["change_kind"] == "terminated"
    history = client.get("/v1/operations/enterprise/organization/history",
                         headers=founder).json()
    assert [x["change_kind"] for x in history["personnel"]][:3] == [
        "terminated", "promoted", "hired"]
    assert history["historical_records_retained"]
    assert client.get("/v1/operations/enterprise/organization/history").status_code == 401
    # M2 can retain archived task records, but terminated AI may never execute new work.
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": agent, "action": "internal:brief"})
    with pytest.raises(Exception, match="Terminated worker"):
        with ctx["db"].transaction():
            ctx["db"].execute(
                "UPDATE ago_governed_tasks SET status='running' WHERE tenant_id=%s AND id=%s",
                (ctx["tenant"], task["id"]),
            )


def test_department_closure_is_non_destructive_and_blocks_new_hires(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = str(uuid4())
    _change(client, founder, reviewer, "created", dept,
            name="Department for Shutdown")
    _change(client, founder, reviewer, "closed", dept)
    with pytest.raises(Exception, match="Closed department cannot hire"):
        with ctx["db"].transaction():
            ctx["db"].execute(
                """INSERT INTO ago_employees(id,tenant_id,department_id,name,kind)
                   VALUES(%s,%s,%s,'Unsafe post-closure AI','ai')""",
                (str(uuid4()), ctx["tenant"], dept),
            )
    assert client.get("/v1/organization/departments", headers=founder).status_code == 200


def test_organizational_promotion_cannot_be_downlevelled_or_self_approved(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = str(uuid4())
    _change(client, founder, reviewer, "created", dept, name="Safe Review Org")
    worker = str(uuid4())
    _change(client, founder, reviewer, "hired", worker,
            department_id=dept, name="Promotable Agent")
    _change(client, founder, reviewer, "promoted", worker, role_level=3)
    request = post(client, "/v1/operations/enterprise/organization/approval",
                   founder, {"change_kind": "promoted", "target_id": worker})
    post(client, "/v1/governance/approvals/" + request["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "self review forbidden"}, expected=403)
    decide(client, reviewer, request["approval_id"])
    post(client, "/v1/operations/enterprise/organization/apply", founder, {
        "change_kind": "promoted", "target_id": worker,
        "approval_id": request["approval_id"], "role_level": 2,
        "reason": "Cannot demote under approved promotion"}, expected=400)
