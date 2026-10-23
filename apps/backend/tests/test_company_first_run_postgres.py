"""Founder first-run acceptance: real signed API, Founder consent, AI task and honest unreviewed QA.

Test uses the disposable database fixture; never touches a founder's local tenant.
"""
from test_m7_http_postgres import case as case, post


def test_first_governed_employee_task_requires_founder_consent_and_qa_evidence(case):
    client, headers, info = case
    founder = headers["founder"]
    reviewer = headers["reviewer"]

    departments = client.get("/v1/organization/departments", headers=founder)
    assert departments.status_code == 200, departments.text
    staff = post(client, "/v1/organization/employees", founder, {
        "department_id": departments.json()[0]["id"],
        "name": "First Run AI Research Specialist",
        "kind": "ai",
    })
    created = post(client, "/v1/tasks", founder, {
        "action": "internal:brief", "assignee_id": staff["id"],
    })
    assert created["status"] == "proposed"
    assert created["assignee_id"] == staff["id"]

    # Neither creating the task nor requesting approval can execute it.
    post(client, f"/v1/agents/tasks/{created['id']}/run", founder, expected=403)
    requested = post(
        client, f"/v1/console/tasks/{created['id']}/request-approval", founder
    )
    assert requested["status"] == "waiting_approval"
    post(client, f"/v1/agents/tasks/{created['id']}/run", founder, expected=403)

    inbox = client.get("/v1/organization/company/approvals", headers=founder)
    assert inbox.status_code == 200, inbox.text
    approval = next(a for a in inbox.json() if a["id"] == requested["approval_id"])
    assert approval["status"] == "pending"
    assert approval["action"] == "internal:brief"
    assert approval["task_id"] == created["id"]

    # A present, registered independent human reviewer must approve an
    # ordinary task. The Founder's own submission cannot self-review it.
    post(client, f"/v1/governance/approvals/{requested['approval_id']}/decision",
         founder, {"approve": True, "reason": "No operational self-review"}, expected=403)
    decided = post(
        client, f"/v1/governance/approvals/{requested['approval_id']}/decision",
        reviewer, {"approve": True, "reason": "Independent human permits internal validation"}
    )
    assert decided["status"] == "approved"

    first = post(client, f"/v1/agents/tasks/{created['id']}/run", founder)
    assert first["status"] == "completed"
    assert first["result"]["requires_human_qa"] is True
    assert first["result"]["kind"] == "internal_brief"
    post(client, f"/v1/agents/tasks/{created['id']}/run", founder, expected=403)

    # No imaginary review occurs on task completion. A separate quality
    # evidence gate stays pending until the CEO-backed QA flow is verified.
    rows = info["db"].execute(
        "SELECT COUNT(*) AS total FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s",
        (info["tenant"], created["id"]),
    ).fetchone()
    assert rows["total"] == 0

    # All persistence belongs to the disposable authenticated test tenant.
    row = info["db"].execute(
        "SELECT status, approval_id FROM ago_governed_tasks WHERE id=%s AND tenant_id=%s",
        (created["id"], info["tenant"]),
    ).fetchone()
    assert row["status"] == "completed"
    assert str(row["approval_id"]) == requested["approval_id"]
