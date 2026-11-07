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
    # Founder rule (issue #8): the Founder is the only human in an AGO company,
    # so company-level requests come to the Founder in every environment and
    # for every governed action, not only small internal validation tasks.
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    for action in ("internal:brief", "tool:review:example", "governance:policy:update"):
        request = post(client, "/v1/governance/approvals", founder, {"action": action})
        done = post(client, "/v1/governance/approvals/" + request["request_id"] + "/decision",
                    founder, {"approve": True, "reason": "Founder decides company request"})
        assert (done["status"], done["reviewer_id"]) == ("approved", info["founder_id"])
    inbox = client.get("/v1/organization/company/approvals", headers=founder).json()
    pending = post(client, "/v1/governance/approvals", founder, {"action": "tool:review:other"})
    inbox = client.get("/v1/organization/company/approvals", headers=founder).json()
    row = next(r for r in inbox if r["id"] == pending["request_id"])
    assert row["founder_solo_mode"] is True and row["decided_by_level"] == "founder"
    assert "Founder decides" in row["review_routing"]
    assert "independent" not in row["review_routing"].lower()


def test_sole_founder_decides_a_standalone_plan_that_had_no_human_reviewer(case):
    """Live case: "First task workflow" (no intake project) waited since 2026-10-20."""
    client, headers, info = case
    founder = headers["founder"]
    info["db"].execute("UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
                       (info["tenant"], info["reviewer_id"]))
    goal = post(client, "/v1/brain/goals", founder,
                {"title": "AI shopping site", "description": "Create an AI shopping site"})
    dept = department(client, founder)
    worker = employee(client, founder, dept)
    plan = post(client, "/v1/brain/plans", founder,
                {"goal_id": goal["id"], "title": "First task workflow"})
    post(client, "/v1/brain/plans/" + plan["id"] + "/steps", founder,
         {"action": "internal:brief", "assignee_id": worker})
    submitted = post(client, "/v1/brain/plans/" + plan["id"] + "/submit", founder)
    decided = post(client, "/v1/governance/approvals/" + submitted["approval_id"] + "/decision",
                   founder, {"approve": True, "reason": "Founder approves the plan"})
    assert decided["status"] == "approved"


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



def test_sole_founder_approved_graph_change_can_be_applied(case):
    from test_sections31_34 import BASE, graph_node, propose

    client, headers, info = case
    founder, db, tenant = headers['founder'], info['db'], info['tenant']
    db.execute("UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
               (tenant, info['reviewer_id']))
    item, _ = propose(client, founder, 'graph', 'node', graph_node(info['founder_id']))
    path = BASE + '/reviews/graph/apply'
    payload = {'proposal_id': item['id']}
    post(client, path, founder, payload, expected=403)
    post(client, '/v1/governance/approvals/'+item['approval_id']+'/decision', founder,
         {'approve': True, 'reason': 'Founder approves company knowledge change'})
    result = post(client, path, founder, payload)
    assert result
    # An already applied proposal returns the same durable revision, not a second write.
    post(client, path, founder, payload)
    assert db.execute("SELECT count(*) AS n FROM ago_enterprise_applied "
                      "WHERE tenant_id=%s AND proposal_id=%s", (tenant, item['id'])).fetchone()['n'] == 1


def test_founder_apply_rechecks_other_human_approver_and_revoked_founder_role(case):
    from test_sections31_34 import BASE, graph_node, propose

    client, headers, info = case
    founder, db, tenant = headers['founder'], info['db'], info['tenant']
    db.execute("UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
               (tenant, info['reviewer_id']))
    item, _ = propose(client, founder, 'graph', 'node', graph_node(info['founder_id']))
    post(client, '/v1/governance/approvals/'+item['approval_id']+'/decision', founder,
         {'approve': True, 'reason': 'Founder approves company knowledge change'})
    path, payload = BASE + '/reviews/graph/apply', {'proposal_id': item['id']}
    db.execute("UPDATE ago_users SET active=true WHERE tenant_id=%s AND id=%s",
               (tenant, info['reviewer_id']))
    post(client, path, founder, payload, expected=403)
    db.execute("UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
               (tenant, info['reviewer_id']))
    db.execute("DELETE FROM ago_user_roles WHERE tenant_id=%s AND user_id=%s AND role='founder'",
               (tenant, info['founder_id']))
    post(client, path, founder, payload, expected=403)
    assert db.execute("SELECT count(*) AS n FROM ago_enterprise_applied "
                      "WHERE tenant_id=%s AND proposal_id=%s", (tenant, item['id'])).fetchone()['n'] == 0
