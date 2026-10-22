"""Founder sovereignty and bounded CEO project-task verification in PostgreSQL."""
from uuid import uuid4

from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee


def test_founder_alone_decides_human_approvals_and_no_member_can_hijack(case):
    client, headers, info = case
    founder, outsider = headers["founder"], headers["reviewer"]
    req = post(client, "/v1/governance/approvals", founder,
               {"action": "internal:brief"})
    path = "/v1/governance/approvals/" + req["request_id"] + "/decision"
    post(client, path, outsider,
         {"approve": True, "reason": "Cannot review Founder work"}, expected=403)
    decided = post(client, path, founder,
                   {"approve": False, "reason": "Founder rejects unscheduled work"})
    assert decided["status"] == "rejected"
    assert decided["reviewer_id"] == info["founder_id"]
    post(client, path, founder,
         {"approve": True, "reason": "Replay blocked"}, expected=400)

    dept = department(client, founder)
    employee(client, founder, dept)
    project = post(client, "/v1/organization/company/projects/start", founder, {
        "brief": "Build a secured accessible workflow with complete test evidence and documented constraints",
        "operation_key": str(uuid4()),
    })
    request = post(client, "/v1/brain/plans/" + project["plan_id"] + "/submit", founder)
    strategic = "/v1/governance/approvals/" + request["approval_id"] + "/decision"
    post(client, strategic, outsider,
         {"approve": True, "reason": "No delegated Founder authority"}, expected=403)
    approved = post(client, strategic, founder,
                    {"approve": True, "reason": "Founder approves complete scope"})
    assert approved["status"] == "approved"
    inbox = client.get("/v1/organization/company/approvals", headers=founder)
    assert inbox.status_code == 200
    assert all("Independent active human reviewer" not in a["review_routing"]
               for a in inbox.json())


def test_ceo_can_verify_only_founder_approved_active_project_internal_task(case):
    client, headers, info = case
    founder, outsider = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    worker = employee(client, founder, dept)
    ceo = post(client, "/v1/organization/employees", founder, {
        "department_id": dept, "name": "Company CEO", "kind": "ai",
    })["id"]
    response = client.put("/v1/organization/company/employees/" + ceo + "/role",
                          headers=founder, json={
                              "role_title": "Chief Executive Officer",
                              "core_responsibilities": "Scope, delivery and risk accountability",
                              "extra_responsibilities": "No external spending or execution rights",
                          })
    assert response.status_code == 200, response.text
    post(client, "/v1/organization/company/board/appoint", founder, {
        "seat": "Strategy & Vision", "employee_id": ceo,
    })
    project = post(client, "/v1/organization/company/projects/start", founder, {
        "brief": "Design and document tested localhost company processes with scoped AI handoff evidence",
        "operation_key": str(uuid4()),
    })
    assert project["stages"][0]["suggested_assignee_id"] == worker
    base = "/v1/organization/company/projects/" + project["id"]
    post(client, base + "/ceo/reconcile", founder, expected=403)
    strategy = post(client, "/v1/brain/plans/" + project["plan_id"] + "/submit", founder)
    post(client, "/v1/governance/approvals/" + strategy["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "One Founder project scope approval"})
    post(client, "/v1/brain/plans/" + project["plan_id"] + "/activate", founder)
    materialized = post(client, "/v1/brain/plans/" + project["plan_id"] + "/materialize", founder)
    task_id = materialized["task_ids"][0]
    approved_none = post(client, base + "/ceo/reconcile", founder)
    assert approved_none["approved_task_ids"] == []
    task = post(client, "/v1/console/tasks/" + task_id + "/request-approval", founder)
    post(client, "/v1/governance/approvals/" + task["approval_id"] + "/decision",
         outsider, {"approve": True, "reason": "No outside human decision"}, expected=403)
    post(client, base + "/ceo/reconcile", outsider, expected=403)
    reconciled = post(client, base + "/ceo/reconcile", founder)
    assert reconciled["ceo_id"] == ceo
    assert reconciled["approved_task_ids"] == [task_id]
    assert reconciled["tasks_executed"] == 0
    assert reconciled["external_tools_authorized"] is False
    # No replayed approval or model run on a second reconciliation.
    assert post(client, base + "/ceo/reconcile", founder)["verified_task_count"] == 0
    receipt = info["db"].execute(
        "SELECT status,reviewer_id FROM ago_approval_requests "
        "WHERE tenant_id=%s AND id=%s", (info["tenant"], task["approval_id"]),
    ).fetchone()
    assert receipt["status"] == "approved"
    assert str(receipt["reviewer_id"]) == ceo
    assert info["db"].execute(
        "SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s AND task_id=%s",
        (info["tenant"], task_id),
    ).fetchone() is None
