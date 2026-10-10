"""End-to-end signed-session, tenant-scoped PostgreSQL Sections 21-27 HTTP journeys.

The independent reviewer is a second active human; each test rolls back the
disposable CI database. No cloud, paid provider or personal Windows DB touched.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from test_m7_http_postgres import case as case, decide, post


def department(client, founder):
    return post(client, "/v1/organization/departments", founder,
                {"name": "Enterprise Section Test " + uuid4().hex[:10]})["id"]


def employee(client, founder, dept):
    return post(client, "/v1/organization/employees", founder,
                {"department_id": dept, "name": "Research Agent", "kind": "ai"})["id"]


def fresh_approval(client, headers, path):
    return post(client, path, headers["founder"])


def test_oos_requires_exact_independent_approval_and_preserves_history(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    assert client.get("/v1/operations/enterprise/modes").status_code == 401
    approval = post(client, "/v1/operations/enterprise/modes/approval", founder,
                    {"target": "paused"})
    payload = {"target": "paused", "approval_id": approval["approval_id"],
               "rationale": "Scheduled safe pause of local worker acquisition",
               "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    post(client, "/v1/operations/enterprise/modes/activate", founder, payload, expected=403)
    post(client, "/v1/governance/approvals/" + approval["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "Self-review"}, expected=403)
    decide(client, reviewer, approval["approval_id"])
    item = post(client, "/v1/operations/enterprise/modes/activate", founder, payload)
    assert item["mode"] == "paused" and item["sequence"] == 1
    assert post(client, "/v1/operations/enterprise/modes/activate",
                founder, payload)["idempotent"] is True
    overview = client.get("/v1/operations/enterprise/modes", headers=founder).json()
    assert overview["effective"]["mode"] == "paused"
    assert len(overview["history"]) == 1
    post(client, "/v1/operations/enterprise/modes/activate",
         founder, {**payload, "target": "emergency"}, expected=403)


def test_agent_state_real_task_links_capacity_and_foreign_employee_denied(case):
    client, headers, _ = case
    founder = headers["founder"]
    dept = department(client, founder)
    agent = employee(client, founder, dept)
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": agent, "action": "internal:brief"})
    url = "/v1/operations/enterprise/agents/" + agent
    state = client.get(url + "/state", headers=founder).json()
    assert state["future_tasks"] == [task["id"]]
    assert state["confidence"] is None and state["subjective_consciousness"] is False
    captured = post(client, url + "/snapshot", founder,
                    {"available_units": 0, "source_ref": "workload:local-operator-review"})
    assert captured["load"]["overloaded"]
    alloc = post(client, url + "/allocation", founder,
                 {"available_units": 10, "source_ref": "workload:operator-input"})
    assert alloc["admitted_task_ids"] == [] and alloc["not_authorized_to_start"]
    assert client.get("/v1/operations/enterprise/agents/" + str(uuid4()) + "/state",
                      headers=founder).status_code == 404
    assert client.get(url + "/state").status_code == 401


def test_nine_horizon_planning_locks_parent_window_and_budget(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    initial = fresh_approval(client, headers, "/v1/operations/enterprise/plans/approval")
    decide(client, reviewer, initial["approval_id"])
    now = datetime.now(timezone.utc)
    plan = {"plan_id": initial["plan_id"], "approval_id": initial["approval_id"],
            "horizon": "lifetime", "title": "Long term research capability",
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=3650)).isoformat(),
            "budget_ceiling": "1000", "evidence_ref": "strategy:founder-reviewed"}
    made = post(client, "/v1/operations/enterprise/plans", founder, plan)
    assert made["horizon"] == "lifetime"
    child = fresh_approval(client, headers, "/v1/operations/enterprise/plans/approval")
    decide(client, reviewer, child["approval_id"])
    payload = {**plan, "plan_id": child["plan_id"], "approval_id": child["approval_id"],
               "parent_id": made["id"], "horizon": "five_year",
               "ends_at": (now + timedelta(days=1825)).isoformat(), "budget_ceiling": "500"}
    post(client, "/v1/operations/enterprise/plans", founder, payload)
    assert len(client.get("/v1/operations/enterprise/plans", headers=founder).json()) == 2
    other = fresh_approval(client, headers, "/v1/operations/enterprise/plans/approval")
    decide(client, reviewer, other["approval_id"])
    post(client, "/v1/operations/enterprise/plans", founder,
         {**payload, "plan_id": other["plan_id"], "approval_id": other["approval_id"],
          "budget_ceiling": "2000"}, expected=403)


def test_economics_unverified_cost_and_independent_hierarchical_budgets(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    now = datetime.now(timezone.utc)
    operation = {"operation_key": "invoice-reference-1", "category": "model",
                 "provider": "unconnected-operator-record", "source_ref": "unverified:source",
                 "amount": "3.20", "currency": "INR",
                 "period_start": (now - timedelta(days=1)).isoformat(),
                 "period_end": now.isoformat()}
    observed = post(client, "/v1/operations/enterprise/costs", founder, operation)
    assert observed["evidence_state"] == "unverified"
    assert post(client, "/v1/operations/enterprise/costs",
                founder, operation)["idempotent"] is True
    post(client, "/v1/operations/enterprise/costs", founder,
         {**operation, "amount": "4"}, expected=400)
    first = fresh_approval(client, headers, "/v1/operations/enterprise/budgets/approval")
    decide(client, reviewer, first["approval_id"])
    b = {"budget_id": first["budget_id"], "approval_id": first["approval_id"],
         "scope_kind": "company", "ceiling": "100", "currency": "INR"}
    assert post(client, "/v1/operations/enterprise/budgets", founder, b)["scope_kind"] == "company"
    dept = department(client, founder)
    child = fresh_approval(client, headers, "/v1/operations/enterprise/budgets/approval")
    decide(client, reviewer, child["approval_id"])
    post(client, "/v1/operations/enterprise/budgets", founder,
         {**b, "budget_id": child["budget_id"], "approval_id": child["approval_id"],
          "scope_kind": "department", "scope_id": dept, "ceiling": "110"}, expected=403)
    post(client, "/v1/operations/enterprise/budgets", founder,
         {**b, "budget_id": child["budget_id"], "approval_id": child["approval_id"],
          "scope_kind": "department", "scope_id": dept, "ceiling": "70"})
    assert len(client.get("/v1/operations/enterprise/costs", headers=founder).json()) == 1


def test_marketplace_draft_human_review_publish_controlled_use_and_isolation(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    payload = {"department_id": dept, "name": "RAG Quality Template", "kind": "template",
               "version": "1.0.0", "license_id": "internal-only",
               "sha256_digest": "d" * 64,
               "manifest": {"purpose": "reviewed internal quality checklist"}}
    item = post(client, "/v1/operations/enterprise/marketplace", founder, payload)
    assert item["status"] == "draft"
    asset = item["id"]
    publish_url = "/v1/operations/enterprise/marketplace/" + asset
    post(client, publish_url + "/publish", founder, expected=403)
    review = post(client, publish_url + "/approval", founder)
    post(client, publish_url + "/publish", founder, expected=403)
    decide(client, reviewer, review["approval_id"])
    assert post(client, publish_url + "/publish", founder)["status"] == "published"
    listings = client.get("/v1/operations/enterprise/marketplace", headers=reviewer).json()
    assert [x["id"] for x in listings if str(x["id"]) == asset]
    usage = post(client, publish_url + "/consume/approval", founder)
    consumption = {"department_id": dept, "approval_id": usage["approval_id"],
                   "evidence_ref": "internal:reusable-safe-template"}
    post(client, publish_url + "/consume", founder, consumption, expected=403)
    decide(client, reviewer, usage["approval_id"])
    assert post(client, publish_url + "/consume", founder, consumption)["execution_granted"] is False
    assert len(client.get("/v1/operations/enterprise/marketplace/usage",
                          headers=founder).json()) == 1
    assert client.get("/v1/operations/enterprise/marketplace").status_code == 401


def test_evolution_has_no_automatic_application_and_twin_is_hypothetical(case):
    client, headers, _ = case
    founder = headers["founder"]
    snap = post(client, "/v1/meta/snapshots", founder)
    comparison = post(client, "/v1/operations/enterprise/evolution/compare", founder,
                      {"snapshot_id": snap["id"], "baseline": ["10", "20"],
                       "candidate": ["12", "15"],
                       "evidence": [{"ref": "qa:one"}, {"ref": "qa:two"}]})
    assert comparison["applied"] is False and comparison["status"] == "unreviewed"
    values = {"snapshot_id": snap["id"], "actions": 10, "cost_per_action": "3",
              "budget": "15", "failure_pct": 20, "hiring": 3, "layoffs": 1,
              "market_shock_pct": -10}
    result = post(client, "/v1/operations/enterprise/twin", founder, values)
    assert result["read_only"] and not result["applied"]
    assert not result["within_budget"]
    assert result["calibration"] == "uncalibrated"
    assert len(client.get("/v1/operations/enterprise/twin", headers=founder).json()) == 1
    post(client, "/v1/operations/enterprise/twin", founder,
         {**values, "snapshot_id": str(uuid4())}, expected=404)


def test_worker_state_reviewed_pause_resume_blocks_real_task_dispatch(case):
    import psycopg
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    agent = employee(client, founder, dept)
    path = "/v1/operations/enterprise/agents/" + agent
    request = post(client, path + "/approval", founder, {"state": "paused"})
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    attempted = {"state": "paused", "approval_id": request["approval_id"],
                 "reason": "QA review pause", "expires_at": expiry}
    post(client, path + "/transition", founder, attempted, expected=403)
    decide(client, reviewer, request["approval_id"])
    paused = post(client, path + "/transition", founder, attempted)
    assert paused["state"] == "paused" and paused["sequence"] == 1
    assert client.get(path + "/state", headers=founder).json()["availability_state"] == "paused"
    task = post(client, "/v1/tasks", founder,
                {"assignee_id": agent, "action": "internal:brief"})
    approval = post(client, "/v1/governance/approvals", founder,
                    {"action": "internal:brief"})
    post(client, f"/v1/tasks/{task['id']}/approval", founder,
         {"approval_id": approval["request_id"]})
    decide(client, reviewer, approval["request_id"])
    with __import__("pytest").raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                "UPDATE ago_governed_tasks SET status='running' WHERE tenant_id=%s AND id=%s",
                (info["tenant"], task["id"]),
            )
    resume = post(client, path + "/approval", founder, {"state": "available"})
    decide(client, reviewer, resume["approval_id"])
    post(client, path + "/transition", founder,
         {"state": "available", "approval_id": resume["approval_id"],
          "reason": "Evidence verified and work may safely resume"})
    assert [h["state"] for h in client.get(path + "/history", headers=founder).json()] == [
        "available", "paused"
    ]
    with info["db"].transaction():
        info["db"].execute(
            "UPDATE ago_governed_tasks SET status='running' WHERE tenant_id=%s AND id=%s",
            (info["tenant"], task["id"]),
        )


def test_published_asset_retirement_halts_new_usage_without_erasing_history(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    item = post(client, "/v1/operations/enterprise/marketplace", founder, {
        "department_id": dept, "name": "Dated Workflow " + uuid4().hex[:8],
        "kind": "workflow", "version": "1.0.0", "license_id": "internal-only",
        "sha256_digest": "a" * 64, "manifest": {"reviewed": True},
    })
    path = "/v1/operations/enterprise/marketplace/" + item["id"]
    request = post(client, path + "/approval", founder)
    decide(client, reviewer, request["approval_id"])
    post(client, path + "/publish", founder)
    retirement = post(client, path + "/lifecycle/approval",
                      founder, {"target_state": "deprecated"})
    payload = {"target_state": "deprecated", "approval_id": retirement["approval_id"],
               "reason": "A newer reviewed version replaces this asset"}
    post(client, path + "/lifecycle", founder, payload, expected=403)
    decide(client, reviewer, retirement["approval_id"])
    assert post(client, path + "/lifecycle", founder, payload)["status"] == "deprecated"
    use = post(client, path + "/consume/approval", founder)
    decide(client, reviewer, use["approval_id"])
    post(client, path + "/consume", founder,
         {"department_id": dept, "approval_id": use["approval_id"],
          "evidence_ref": "test:post-retirement"}, expected=403)
    listed = client.get("/v1/operations/enterprise/marketplace", headers=founder).json()
    assert next(a["status"] for a in listed if str(a["id"]) == item["id"]) == "deprecated"


def test_digital_twin_uses_frozen_snapshot_not_live_workforce(case):
    client, headers, info = case
    founder = headers["founder"]
    snapshot = post(client, "/v1/meta/snapshots", founder)
    historical = info["db"].execute(
        "SELECT metrics FROM ago_executive_snapshots WHERE tenant_id=%s AND id=%s",
        (info["tenant"], snapshot["id"]),
    ).fetchone()["metrics"]["organization_observation"]["ai_employees"]
    dept = department(client, founder)
    employee(client, founder, dept)
    scenario = post(client, "/v1/operations/enterprise/twin", founder, {
        "snapshot_id": snapshot["id"], "actions": 5,
        "cost_per_action": "1", "budget": "20", "failure_pct": 10,
        "hiring": 0, "layoffs": 0, "market_shock_pct": 0,
    })
    assert scenario["snapshot_workers"] == historical
    assert scenario["hypothetical_workers"] == historical
    assert scenario["snapshot_source"] == "immutable_executive_metrics"
    assert scenario["read_only"] is True and scenario["applied"] is False
