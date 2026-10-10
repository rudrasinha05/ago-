"""Section 21 real PostgreSQL capacity, independent review and race-safe admission.

No mocked worker capacity: starting actual governed tasks passes through the
same database trigger that the AgentRuntime and TaskStore use.
"""
import pytest

from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, decide, post


def _reviewed_capacity(client, founder, reviewer, scope_kind, scope_id, cap):
    base = {"scope_kind": scope_kind, "scope_id": scope_id, "max_running": cap}
    req = post(client, "/v1/operations/enterprise/capacity/approval", founder, base)
    full = {**base, "approval_id": req["approval_id"],
            "rationale": "Bounded independently reviewed worker throughput"}
    post(client, "/v1/operations/enterprise/capacity", founder, full, expected=403)
    decide(client, reviewer, req["approval_id"])
    result = post(client, "/v1/operations/enterprise/capacity", founder, full)
    assert result["max_running"] == cap and not result["idempotent"]
    assert post(client, "/v1/operations/enterprise/capacity",
                founder, full)["idempotent"] is True
    return result


def _approved_task(client, founder, reviewer, employee_id):
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": employee_id, "action": "internal:brief"})
    review = post(client, "/v1/governance/approvals", founder,
                  {"action": "internal:brief"})
    post(client, f"/v1/tasks/{task['id']}/approval", founder,
         {"approval_id": review["request_id"]})
    decide(client, reviewer, review["request_id"])
    return task["id"]


def test_actual_task_start_is_capacity_bounded_and_released_after_completion(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    agent = employee(client, founder, dept)
    first = _approved_task(client, founder, reviewer, agent)
    second = _approved_task(client, founder, reviewer, agent)
    def update(task_id, new_state):
        with ctx["db"].transaction():
            ctx["db"].execute(
                "UPDATE ago_governed_tasks SET status=%s WHERE tenant_id=%s AND id=%s",
                (new_state, ctx["tenant"], task_id),
            )
    update(first, "running")
    with pytest.raises(Exception, match="OOS running capacity exceeded"):
        update(second, "running")
    _reviewed_capacity(client, founder, reviewer, "employee", agent, 2)
    update(second, "running")
    state = client.get("/v1/operations/enterprise/capacity", headers=founder).json()
    assert state["total_running"] == 2
    assert state["changes_require_independent_review"]
    update(first, "completed")
    assert client.get("/v1/operations/enterprise/capacity",
                      headers=founder).json()["total_running"] == 1
    assert client.get("/v1/operations/enterprise/capacity").status_code == 401


def test_department_capacity_blocks_two_different_employee_tasks(case):
    client, headers, ctx = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    a, b = employee(client, founder, dept), employee(client, founder, dept)
    _reviewed_capacity(client, founder, reviewer, "department", dept, 1)
    first = _approved_task(client, founder, reviewer, a)
    second = _approved_task(client, founder, reviewer, b)
    with ctx["db"].transaction():
        ctx["db"].execute(
            "UPDATE ago_governed_tasks SET status='running' WHERE tenant_id=%s AND id=%s",
            (ctx["tenant"], first),
        )
    with pytest.raises(Exception, match="OOS running capacity exceeded"):
        with ctx["db"].transaction():
            ctx["db"].execute(
                "UPDATE ago_governed_tasks SET status='running' WHERE tenant_id=%s AND id=%s",
                (ctx["tenant"], second),
            )


def test_capacity_limit_requires_real_reviewer_and_tenant_target(case):
    from uuid import uuid4

    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    req = post(client, "/v1/operations/enterprise/capacity/approval", founder,
               {"scope_kind": "company", "max_running": 5})
    post(client, "/v1/governance/approvals/" + req["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "Self-approval forbidden"}, expected=403)
    decide(client, reviewer, req["approval_id"])
    post(client, "/v1/operations/enterprise/capacity", founder,
         {"scope_kind": "company", "max_running": 6,
          "approval_id": req["approval_id"], "rationale": "Changed capacity"}, expected=403)
    post(client, "/v1/operations/enterprise/capacity", founder,
         {"scope_kind": "employee", "scope_id": str(uuid4()), "max_running": 2,
          "approval_id": req["approval_id"], "rationale": "Changed scope"}, expected=403)
