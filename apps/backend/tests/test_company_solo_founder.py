"""Single active human Founder controls approval despite other account presence."""
from uuid import uuid4

from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee


def test_founder_can_approve_or_deny_without_other_human_or_legacy_flags(case, monkeypatch):
    client, headers, info = case
    founder, outsider = headers["founder"], headers["reviewer"]
    monkeypatch.delenv("AGO_FOUNDER_SOLO_APPROVAL", raising=False)
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    # Only a genuinely sole active founder can self-authorize small internal
    # validation. Deactivate the fixture's separate human reviewer first.
    info["db"].execute(
        "UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["reviewer_id"]),
    )
    for decision in (True, False):
        proposal = post(client, "/v1/governance/approvals", founder,
                        {"action": "internal:brief"})
        path = "/v1/governance/approvals/" + proposal["request_id"] + "/decision"
        # Disabled reviewer has an invalid signed session, not merely RBAC denial.
        post(client, path, outsider,
             {"approve": decision, "reason": "Inactive reviewer cannot authenticate"}, expected=401)
        result = post(client, path, founder, {
            "approve": decision, "reason": "Founder controls company request"
        })
        assert result["status"] == ("approved" if decision else "rejected")
        assert result["reviewer_id"] == info["founder_id"]
        post(client, path, founder,
             {"approve": not decision, "reason": "No re-decision"}, expected=400)
        assert info["db"].execute("""
            SELECT 1 FROM ago_approval_audit
            WHERE tenant_id=%s AND request_id=%s
              AND actor_id=%s AND event=%s
        """, (info["tenant"], proposal["request_id"], info["founder_id"],
              "approved" if decision else "rejected")).fetchone()
    assert client.post(path, json={"approve": True, "reason": "Anonymous"}).status_code == 401
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    production = post(client, "/v1/governance/approvals", founder,
                      {"action": "internal:brief"})
    post(client, "/v1/governance/approvals/" + production["request_id"] + "/decision",
         founder, {"approve": True, "reason": "Production self-review prohibited"},
         expected=403)


def test_human_reviewer_can_review_operations_but_cannot_take_founder_role(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    req = post(client, "/v1/governance/approvals", founder,
               {"action": "tool:review:example"})
    path = "/v1/governance/approvals/" + req["request_id"] + "/decision"
    post(client, path, founder,
         {"approve": True, "reason": "Operational self review denied"}, expected=403)
    done = post(client, path, reviewer,
                {"approve": True, "reason": "Authenticated independent human review"})
    assert done["status"] == "approved"
    assert done["reviewer_id"] == info["reviewer_id"]
    assert done["reviewer_id"] != info["founder_id"]


def test_project_quality_stage_uses_real_ai_specialist_not_a_third_party(case):
    client, headers, info = case
    founder = headers["founder"]
    dept = department(client, founder)
    pm = post(client, "/v1/organization/employees", founder, {
        "department_id": dept, "name": "Project Manager", "kind": "ai",
    })["id"]
    response = client.put("/v1/organization/company/employees/" + pm + "/role",
                          headers=founder, json={
                              "role_title": "Project Manager",
                              "core_responsibilities": "Accountable for delivery",
                              "extra_responsibilities": "Escalate QA blockers to CEO",
                          })
    assert response.status_code == 200
    worker = employee(client, founder, dept)
    implementer = post(client, "/v1/organization/employees", founder, {
        "department_id": dept, "name": "Software Developer", "kind": "ai",
    })["id"]
    qa = post(client, "/v1/organization/employees", founder, {
        "department_id": dept, "name": "Quality Engineer", "kind": "ai",
    })["id"]
    assert implementer != qa
    project = post(client, "/v1/organization/company/projects/start", founder, {
        "brief": "Build testable local software with real QA specialist evidence and CEO reporting",
        "operation_key": str(uuid4()),
    })
    assert project["accountable_manager_id"] == pm
    implementation_stage = next(s for s in project["stages"]
                                if s["stage"] == "implementation")
    assert implementation_stage["suggested_assignee_id"] == implementer
    stage = next(s for s in project["stages"] if s["stage"] == "quality")
    assert stage["suggested_assignee_id"] != info["founder_id"]
    endpoint = "/v1/organization/company/projects/" + project["id"] + "/delegations"
    proposal = post(client, endpoint, founder, {
        "stage": "quality", "assignee_id": qa,
    })
    assert proposal["status"] == "pending_founder_decision"
    post(client, endpoint, founder, {
        "stage": "quality", "assignee_id": info["founder_id"],
    }, expected=403)
    post(client, "/v1/governance/approvals/" + proposal["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "Founder records real QA specialist"})
    strategy = post(client, "/v1/brain/plans/" + project["plan_id"] + "/submit", founder)
    post(client, "/v1/governance/approvals/" + strategy["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "Founder project scope approval"})
    post(client, "/v1/brain/plans/" + project["plan_id"] + "/activate", founder)
    actual = post(client, endpoint + "/" + proposal["proposal_id"] + "/activate", founder)
    assert actual["assignee_id"] == qa
    assert actual["task_executed"] is False
    assert worker != qa


def test_staffing_does_not_invent_human_reviewers(case):
    client, headers, info = case
    founder = headers["founder"]
    dept = department(client, founder)
    pm = post(client, "/v1/organization/employees", founder, {
        "department_id": dept, "name": "Delivery Manager", "kind": "ai",
    })["id"]
    client.put("/v1/organization/company/employees/" + pm + "/role",
               headers=founder, json={
                   "role_title": "Project Manager",
                   "core_responsibilities": "Own governed delivery",
                   "extra_responsibilities": "QA risk escalation",
               })
    project = post(client, "/v1/organization/company/projects/start", founder, {
        "brief": "Build local product with no fictitious QA specialist and verifiable results",
        "operation_key": str(uuid4()),
    })
    report = client.get("/v1/organization/company/management/workload", headers=founder)
    assert report.status_code == 200
    rows = [x for x in report.json()["unassigned_project_stages"]
            if x["project_id"] == project["id"] and x["stage"] == "quality"]
    assert rows and rows[0]["founder_local_qa_candidate"] is False
    assert report.json()["staffing_decisions_executed"] == 0
