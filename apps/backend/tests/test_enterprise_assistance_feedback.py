"""Real PostgreSQL HTTP acceptance: assisted employee refusal and reviewed plan feedback.

All calls operate inside existing rolled-back CI cases. An AI's concern cannot
grant it authorization, and plan lineage cannot bypass independent task QA.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, decide, post


def test_blocking_assistance_refuses_actual_task_until_independently_resolved(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    agent = employee(client, founder, dept)
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": agent, "action": "internal:brief"})
    task_approval = post(client, "/v1/governance/approvals", founder,
                         {"action": "internal:brief"})
    post(client, f"/v1/tasks/{task['id']}/approval", founder,
         {"approval_id": task_approval["request_id"]})
    decide(client, reviewer, task_approval["request_id"])
    request = post(client, "/v1/operations/enterprise/assistance", founder, {
        "employee_id": agent, "task_id": task["id"],
        "reason": "overload", "severity": "blocking",
        "summary": "Task capacity and QA evidence need manual review",
        "evidence_ref": "tasks:" + task["id"],
    })
    assert request["execution_guard"] and request["status"] == "open"
    state = client.get("/v1/operations/enterprise/agents/" + agent + "/state",
                       headers=founder).json()
    assert state["help_needed"] is True and state["blocking_assistance"] == 1
    with pytest.raises(Exception, match="Blocking assistance"):
        with ctx["db"].transaction():
            ctx["db"].execute(
                """UPDATE ago_governed_tasks SET status='running'
                   WHERE tenant_id=%s AND id=%s""", (ctx["tenant"], task["id"]),
            )
    endpoint = "/v1/operations/enterprise/assistance/" + request["id"]
    approval = post(client, endpoint + "/approval", founder)
    resolution = {"approval_id": approval["approval_id"], "outcome": "resolved",
                  "explanation": "Second human verified capacity and permission"}
    post(client, endpoint + "/resolve", founder, resolution, expected=403)
    post(client, "/v1/governance/approvals/" + approval["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "Self review is forbidden"}, expected=403)
    decide(client, reviewer, approval["approval_id"])
    finished = post(client, endpoint + "/resolve", founder, resolution)
    assert finished["outcome"] == "resolved"
    assert post(client, endpoint + "/resolve", founder, resolution)["idempotent"]
    with ctx["db"].transaction():
        ctx["db"].execute(
            """UPDATE ago_governed_tasks SET status='running'
               WHERE tenant_id=%s AND id=%s""", (ctx["tenant"], task["id"]),
        )
    rows = client.get("/v1/operations/enterprise/assistance",
                      headers=founder).json()
    assert rows[0]["outcome"] == "resolved"
    state = client.get("/v1/operations/enterprise/agents/" + agent + "/state",
                       headers=founder).json()
    assert state["blocking_assistance"] == 0
    assert client.get("/v1/operations/enterprise/assistance").status_code == 401


def test_assistance_rejects_foreign_task_and_rejection_remains_blocking(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    agent = employee(client, founder, dept)
    other = employee(client, founder, dept)
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": other, "action": "internal:brief"})
    base = {"employee_id": agent, "task_id": task["id"], "reason": "safety_risk",
            "severity": "blocking", "summary": "Unsafe task",
            "evidence_ref": "qa:failed-check"}
    post(client, "/v1/operations/enterprise/assistance", founder, base, expected=403)
    request = post(client, "/v1/operations/enterprise/assistance", founder,
                   {**base, "task_id": None})
    url = "/v1/operations/enterprise/assistance/" + request["id"]
    approval = post(client, url + "/approval", founder)
    decide(client, reviewer, approval["approval_id"])
    post(client, url + "/resolve", founder,
         {"approval_id": approval["approval_id"], "outcome": "rejected",
          "explanation": "Insufficient evidence; keep worker blocked"})
    state = client.get("/v1/operations/enterprise/agents/" + agent + "/state",
                       headers=founder).json()
    assert state["blocking_assistance"] == 1


def test_horizon_feedback_counts_real_links_without_inventing_qa(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    agent = employee(client, founder, dept)
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": agent, "action": "internal:brief"})
    review = post(client, "/v1/operations/enterprise/plans/approval", founder)
    decide(client, reviewer, review["approval_id"])
    now = datetime.now(timezone.utc)
    plan = post(client, "/v1/operations/enterprise/plans", founder, {
        "plan_id": review["plan_id"], "approval_id": review["approval_id"],
        "horizon": "lifetime", "title": "Company long-term goal",
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=3650)).isoformat(),
        "budget_ceiling": "500", "evidence_ref": "goal:reviewed"
    })
    prefix = f"/v1/operations/enterprise/plans/{plan['id']}"
    empty = client.get(prefix + "/feedback", headers=founder).json()
    assert empty["linked_tasks"] == 0 and empty["status"] == "no_evidence"
    approval = post(client, prefix + f"/tasks/{task['id']}/approval", founder)
    payload = {"approval_id": approval["approval_id"],
               "evidence_ref": "tasks:" + task["id"]}
    post(client, prefix + f"/tasks/{task['id']}/link", founder, payload, expected=403)
    decide(client, reviewer, approval["approval_id"])
    linked = post(client, prefix + f"/tasks/{task['id']}/link", founder, payload)
    assert linked["execution_authorized"] is False
    assert post(client, prefix + f"/tasks/{task['id']}/link",
                founder, payload)["idempotent"]
    feedback = client.get(prefix + "/feedback", headers=founder).json()
    assert feedback["linked_tasks"] == 1
    assert feedback["awaiting_qa"] == 1
    assert feedback["qa_passed"] == 0
    assert feedback["automatically_replanned"] is False
    assert client.get(f"/v1/operations/enterprise/plans/{uuid4()}/feedback",
                      headers=founder).status_code == 404
