"""Explicit local sole-founder approvals preserve tenant and audit protections."""
from test_m7_http_postgres import case as case, post


def test_sole_human_founder_can_approve_without_second_account(case, monkeypatch):
    client, headers, info = case
    founder = headers["founder"]
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_FOUNDER_SOLO_APPROVAL", "true")
    req = post(client, "/v1/governance/approvals", founder, {"action": "internal:brief"})
    path = "/v1/governance/approvals/" + req["request_id"] + "/decision"
    # Still independent when another real human reviewer exists.
    post(client, path, founder, {"approve": True, "reason": "No self-review"}, expected=403)
    info["db"].execute(
        "UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["reviewer_id"]),
    )
    inbox = client.get("/v1/organization/company/approvals", headers=founder)
    assert inbox.status_code == 200, inbox.text
    entry = next(x for x in inbox.json() if x["id"] == req["request_id"])
    assert entry["founder_solo_mode"] is True
    assert "Founder-only local authority" in entry["review_routing"]
    result = post(client, path, founder,
                  {"approve": True, "reason": "Sole human founder reviewed scoped work"})
    assert result["status"] == "approved"
    assert result["reviewer_id"] == info["founder_id"]
    assert info["db"].execute("""
        SELECT 1 FROM ago_approval_audit WHERE tenant_id=%s AND request_id=%s
           AND actor_id=%s AND event='approved'
    """, (info["tenant"], req["request_id"], info["founder_id"])).fetchone()
    post(client, path, founder, {"approve": False, "reason": "No re-decision"}, expected=400)


def test_solo_mode_rejects_production_and_disabled_option(case, monkeypatch):
    client, headers, info = case
    founder = headers["founder"]
    info["db"].execute(
        "UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["reviewer_id"]),
    )
    req = post(client, "/v1/governance/approvals", founder, {"action": "internal:brief"})
    path = "/v1/governance/approvals/" + req["request_id"] + "/decision"
    monkeypatch.delenv("AGO_FOUNDER_SOLO_APPROVAL", raising=False)
    post(client, path, founder, {"approve": False, "reason": "No opt-in"}, expected=403)
    monkeypatch.setenv("AGO_FOUNDER_SOLO_APPROVAL", "true")
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    post(client, path, founder, {"approve": False, "reason": "Never on production"}, expected=403)
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    result = post(client, path, founder,
                  {"approve": False, "reason": "Founder explicitly denied operation"})
    assert result["status"] == "rejected"
    assert client.post(path, json={"approve": True, "reason": "Anonymous"}).status_code == 401


def test_solo_mode_never_enables_self_approval_when_reviewer_exists(case, monkeypatch):
    client, headers, info = case
    monkeypatch.setenv("AGO_FOUNDER_SOLO_APPROVAL", "true")
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    founder, reviewer = headers["founder"], headers["reviewer"]
    req = post(client, "/v1/governance/approvals", founder,
               {"action": "tool:review:example"})
    path = "/v1/governance/approvals/" + req["request_id"] + "/decision"
    post(client, path, founder, {"approve": True, "reason": "Must stay independent"}, expected=403)
    approved = post(client, path, reviewer,
                    {"approve": True, "reason": "Actual active human decision"})
    assert approved["status"] == "approved"
    assert approved["reviewer_id"] == info["reviewer_id"]


def test_solo_founder_is_actual_quality_stage_owner_without_fake_reviewer(case, monkeypatch):
    from uuid import uuid4
    from test_enterprise_http_21_27 import department
    client, headers, info = case
    founder = headers["founder"]
    monkeypatch.setenv("AGO_FOUNDER_SOLO_APPROVAL", "true")
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    info["db"].execute(
        "UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["reviewer_id"]),
    )
    dept = department(client, founder)
    pm = post(client, "/v1/organization/employees", founder,
              {"department_id":dept,"name":"Project Manager","kind":"ai"})["id"]
    profile = client.put("/v1/organization/company/employees/"+pm+"/role",
                         headers=founder,json={
                             "role_title":"Project Manager",
                             "core_responsibilities":"Accountable approved project delivery",
                             "extra_responsibilities":"Record QA and manager reporting"})
    assert profile.status_code==200,profile.text
    post(client, "/v1/organization/employees", founder,
         {"department_id":dept,"name":"Research Analyst","kind":"ai"})
    project = post(client, "/v1/organization/company/projects/start", founder,
                   {"brief":"Deliver secure AI company software with real QA and tracked tasks",
                    "operation_key":str(uuid4())})
    assert project["accountable_manager_id"] == pm
    quality = next(s for s in project["stages"] if s["stage"]=="quality")
    assert quality["suggested_assignee_id"] == info["founder_id"]
    endpoint = "/v1/organization/company/projects/" + project["id"] + "/delegations"
    proposed = post(client, endpoint, founder,
                    {"stage":"quality", "assignee_id":info["founder_id"]})
    assert proposed["status"] == "pending_founder_decision"
    approved = post(client,
                    "/v1/governance/approvals/" + proposed["approval_id"] + "/decision",
                    founder, {"approve":True, "reason":"Independent of AI delivery manager"})
    assert approved["status"]=="approved"
    strategy = post(client, "/v1/brain/plans/" + project["plan_id"] + "/submit", founder)
    post(client, "/v1/governance/approvals/" + strategy["approval_id"] + "/decision",
         founder, {"approve":True, "reason":"Authorize founder scope"})
    post(client, "/v1/brain/plans/" + project["plan_id"] + "/activate", founder)
    activated = post(client, endpoint + "/" + proposed["proposal_id"] + "/activate",
                     founder)
    assert activated["assignee_id"] == info["founder_id"]
    assert activated["task_executed"] is False


def test_legacy_unstaffed_quality_suggests_local_founder_without_fake_assignment(case, monkeypatch):
    from uuid import uuid4
    from test_enterprise_http_21_27 import department
    client, headers, info = case
    founder = headers["founder"]
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.delenv("AGO_FOUNDER_SOLO_APPROVAL", raising=False)
    info["db"].execute(
        "UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["reviewer_id"]),
    )
    dept=department(client,founder)
    pm=post(client,"/v1/organization/employees",founder,
            {"department_id":dept,"name":"Delivery Manager AI","kind":"ai"})["id"]
    response=client.put("/v1/organization/company/employees/"+pm+"/role",
                        headers=founder,json={
                          "role_title":"Project Manager",
                          "core_responsibilities":"Oversee governed delivery",
                          "extra_responsibilities":"Arrange authorized QA"})
    assert response.status_code==200,response.text
    project=post(client,"/v1/organization/company/projects/start",founder,
                 {"brief":"Build a local product with reviewed software QA and honest evidence",
                  "operation_key":str(uuid4())})
    quality=next(s for s in project["stages"] if s["stage"]=="quality")
    assert quality["suggested_assignee_id"] is None
    monkeypatch.setenv("AGO_FOUNDER_SOLO_APPROVAL","true")
    report=client.get("/v1/organization/company/management/workload",headers=founder)
    assert report.status_code==200,report.text
    vacancy=next(v for v in report.json()["unassigned_project_stages"]
                 if v["stage"]=="quality" and v["project_id"]==project["id"])
    assert vacancy["candidate_id"] == info["founder_id"]
    assert vacancy["founder_local_qa_candidate"] is True
    assert report.json()["staffing_decisions_executed"] == 0
    saved=info["db"].execute("""
      SELECT suggested_assignee_id FROM ago_founder_intake_stages
      WHERE tenant_id=%s AND intake_id=%s AND stage='quality'
    """,(info["tenant"],project["id"])).fetchone()
    assert saved["suggested_assignee_id"] is None
