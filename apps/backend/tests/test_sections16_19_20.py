"""Real session/PostgreSQL architecture, culture inheritance and outcome review."""
import time
from uuid import uuid4

import pytest

from test_m7_http_postgres import case as case, decide, post, profile
from ago.dna_domain import DEFAULT_CHARTER, CORE_GUARDS


def proposal(client, headers, *, scope_kind="company", scope_id=None, charter=None,
             thresholds=None):
    return post(client, "/v1/meta/dna", headers, {
        "profile": thresholds or profile(), "rationale": "Evidence-based scoped culture change",
        "scope_kind": scope_kind, "scope_id": scope_id,
        "charter": charter if charter is not None else dict(DEFAULT_CHARTER)
                   if scope_kind == "company" else {},
    })


def activate(client, headers, item):
    decide(client, headers["reviewer"], item["approval_id"])
    return post(client, f"/v1/meta/dna/{item['id']}/reconcile", headers["founder"])


def team(client, founder):
    department = post(client, "/v1/organization/departments", founder, {"name": "Research"})
    employee = post(client, "/v1/organization/employees", founder, {
        "department_id": department["id"], "name": "Evidence AI", "kind": "ai"})
    return department, employee


def complete_task(client, headers, employee, *, review=True):
    f, r = headers["founder"], headers["reviewer"]
    task = post(client, "/v1/tasks", f, {"assignee_id": employee["id"], "action": "internal:brief"})
    a = post(client, "/v1/governance/approvals", f, {"action": "internal:brief"})
    post(client, f"/v1/tasks/{task['id']}/approval", f, {"approval_id": a["request_id"]})
    decide(client, r, a["request_id"])
    run = post(client, f"/v1/agents/tasks/{task['id']}/run", f)
    if review:
        post(client, f"/v1/tasks/{task['id']}/review", r,
             {"verdict": "pass", "evidence": "Independent evidence inspection"})
    return task, run


def test_full_charter_inheritance_and_actual_execution_provenance(case):
    c, h, info = case
    charter = {**DEFAULT_CHARTER, "mission": "Reproducible local research for the founder."}
    parent = proposal(c, h["founder"], charter=charter)
    activate(c, h, parent)
    d, e = team(c, h["founder"])
    child = proposal(c, h["founder"], scope_kind="department", scope_id=d["id"],
        charter={"communication_style": "Explain results in plain Hinglish."},
        thresholds=profile(qa_target_pct=90, backlog_limit=3))
    activate(c, h, child)
    individual = proposal(c, h["founder"], scope_kind="employee", scope_id=e["id"],
        charter={"learning_philosophy": "Retain sources and correct outdated evidence."},
        thresholds=profile(qa_target_pct=95, backlog_limit=2))
    activate(c, h, individual)
    effective = c.get("/v1/meta/dna/effective", params={"employee_id": e["id"]},
                      headers=h["founder"]).json()
    assert effective["charter"]["mission"] == charter["mission"]
    assert effective["charter"]["communication_style"] == "Explain results in plain Hinglish."
    assert [x["scope"] for x in effective["lineage"]] == ["company", "department", "employee"]
    assert effective["profile"]["qa_target_pct"] == 95
    assert effective["guards"] == CORE_GUARDS
    _, run = complete_task(c, h, e)
    row = info["db"].execute("SELECT dna_context FROM ago_agent_runs WHERE id=%s", (run["id"],)).fetchone()
    assert row["dna_context"] == effective
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
        info["db"].execute("UPDATE ago_agent_runs SET dna_context='{}'::jsonb WHERE id=%s", (run["id"],))


def test_dna_cannot_override_constitution_weaken_parent_or_cross_tenant(case):
    c, h, info = case
    d, e = team(c, h["founder"])
    for charter in ({"mission": "Different authority"}, {"disable_human_approval": "true"},
                    {"security_philosophy": "Remove access checks"}):
        post(c, "/v1/meta/dna", h["founder"], {"profile": profile(), "rationale": "Illegal override",
             "scope_kind": "employee", "scope_id": e["id"], "charter": charter}, expected=400)
    post(c, "/v1/meta/dna", h["founder"], {"profile": profile(qa_target_pct=50),
         "rationale": "Weakening quality", "scope_kind": "department", "scope_id": d["id"],
         "charter": {}}, expected=403)
    post(c, "/v1/meta/dna", h["reviewer"], {"profile": profile(),
         "rationale": "Unauthorized mutation"}, expected=403)
    assert c.get("/v1/meta/dna/effective", params={"employee_id": str(uuid4())},
                 headers=h["founder"]).status_code == 404
    from ago.bootstrap import bootstrap
    from ago.organization_store import OrganizationStore
    other, _ = bootstrap(info["db"], organization="Other", email="other@example.test",
                          password="other-password-123")
    foreign = OrganizationStore(info["db"]).add_department(tenant_id=other, name="Foreign")
    post(c, "/v1/meta/dna", h["founder"], {"profile": profile(), "rationale": "Foreign target",
         "scope_kind": "department", "scope_id": foreign.id, "charter": {}}, expected=404)


def test_parent_change_invalidates_weaker_child_and_pending_activation(case):
    c, h, info = case
    d, e = team(c, h["founder"])
    child = proposal(c, h["founder"], scope_kind="department", scope_id=d["id"],
                     thresholds=profile(qa_target_pct=90))
    activate(c, h, child)
    pending = proposal(c, h["founder"], scope_kind="employee", scope_id=e["id"],
                       thresholds=profile(qa_target_pct=90))
    parent = proposal(c, h["founder"], thresholds=profile(qa_target_pct=95))
    activate(c, h, parent)
    activate_result = c.get("/v1/meta/dna/effective", params={"employee_id": e["id"]},
                           headers=h["founder"]).json()
    assert activate_result["profile"]["qa_target_pct"] == 95
    assert activate_result["ignored"][0]["id"] == child["id"]
    decide(c, h["reviewer"], pending["approval_id"])
    post(c, f"/v1/meta/dna/{pending['id']}/reconcile", h["founder"], expected=403)
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
        info["db"].execute("UPDATE ago_dna_versions SET status='active',activated_at=now() WHERE id=%s",
                           (pending["id"],))
    with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
        info["db"].execute("UPDATE ago_dna_versions SET charter='{}'::jsonb WHERE id=%s", (parent["id"],))


def test_reflection_and_independently_reviewed_real_outcome_delta(case):
    c, h, info = case
    d, e = team(c, h["founder"])
    complete_task(c, h, e, review=False)
    before = post(c, "/v1/meta/snapshots", h["founder"])
    rec = post(c, f"/v1/meta/snapshots/{before['id']}/recommendations", h["founder"])[0]
    decide(c, h["reviewer"], rec["approval_id"])
    post(c, f"/v1/meta/recommendations/{rec['id']}/reconcile", h["founder"])
    complete_task(c, h, e, review=True)
    after = post(c, "/v1/meta/snapshots", h["founder"])
    outcome = post(c, "/v1/meta/evaluations", h["founder"], {
        "recommendation_id": rec["id"], "after_id": after["id"],
        "change_evidence": "Independent QA added to the second real completed task."})
    assert outcome["assessment"]["observed_delta"]["quality_pct"] == "50.00"
    assert outcome["assessment"]["sufficient_outcomes"]
    assert not outcome["assessment"]["causal_effect_proven"]
    url = f"/v1/meta/evaluations/{outcome['id']}/reconcile"
    post(c, url, h["founder"], expected=403)
    post(c, f"/v1/governance/approvals/{outcome['approval_id']}/decision", h["founder"],
         {"approve": True, "reason": "Self-review"}, expected=403)
    decide(c, h["reviewer"], outcome["approval_id"])
    assert post(c, url, h["founder"])["status"] == "verified"
    post(c, url, h["founder"], expected=403)
    started = time.monotonic()
    response = c.get("/v1/meta/reflection", headers=h["reviewer"])
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "observed" and report["sample_count"] == 2
    assert set(report["dimensions"]) == {"organization", "architecture", "departments", "workforce", "workflows"}
    assert report["dimensions"]["architecture"]["passed"]
    assert report["dimensions"]["departments"]
    assert len(report["reviewed_evaluations"]) == 1
    assert report["automatic_execution"] is False
    assert time.monotonic() - started < 3, "Bounded two-snapshot reflection regression"
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
        info["db"].execute("UPDATE ago_meta_evaluations SET change_evidence='rewrite' WHERE id=%s",
                           (outcome["id"],))


def test_invalid_evaluation_order_unendorsed_and_cross_tenant_sources(case):
    c, h, info = case
    before = post(c, "/v1/meta/snapshots", h["founder"])
    rec = post(c, f"/v1/meta/snapshots/{before['id']}/recommendations", h["founder"])[0]
    data = {"recommendation_id": rec["id"], "after_id": before["id"], "change_evidence": "No change"}
    post(c, "/v1/meta/evaluations", h["founder"], data, expected=403)
    decide(c, h["reviewer"], rec["approval_id"])
    post(c, f"/v1/meta/recommendations/{rec['id']}/reconcile", h["founder"])
    post(c, "/v1/meta/evaluations", h["founder"], data, expected=403)
    data["after_id"] = str(uuid4())
    post(c, "/v1/meta/evaluations", h["founder"], data, expected=404)
    from ago.bootstrap import bootstrap
    from ago.executive_intelligence import ExecutiveIntelligence
    other, author = bootstrap(info["db"], organization="Foreign evidence",
                              email="foreign-evidence@example.test", password="foreign-password-123")
    foreign = ExecutiveIntelligence(info["db"]).capture(tenant_id=other, analyst_id=author)
    data["after_id"] = foreign["id"]
    post(c, "/v1/meta/evaluations", h["founder"], data, expected=404)
    assert c.get("/v1/meta/reflection?limit=1000", headers=h["founder"]).status_code == 422
    assert c.get("/v1/meta/reflection").status_code == 401


def test_architecture_change_review_has_immutable_evidence_and_no_auto_apply(case):
    c, h, info = case
    spec = {"sections": [12, 14, 16], "baseline_digest": "a" * 64,
            "candidate_digest": "b" * 64, "rationale": "Review a scoped dependency",
            "impact": "Strategy boundary only", "rollback": "Retain prior manifest and code",
            "evidence_ref": "git:reviewable-contract-diff"}
    change = post(c, "/v1/meta/architecture/changes", h["founder"],
                  {"change_key": "ARCH-120", "specification": spec})
    url = f"/v1/meta/architecture/changes/{change['id']}/reconcile"
    post(c, url, h["founder"], expected=403)
    decide(c, h["reviewer"], change["approval_id"])
    result = post(c, url, h["founder"])
    assert result["status"] == "accepted" and result["applied"] is False
    rows = c.get("/v1/meta/architecture/changes", headers=h["reviewer"]).json()
    assert rows[0]["specification"] == spec
    post(c, url, h["founder"], expected=403)
    post(c, "/v1/meta/architecture/changes", h["founder"],
         {"change_key": "ARCH-120", "specification": spec}, expected=400)
    rejected = post(c, "/v1/meta/architecture/changes", h["founder"],
                    {"change_key": "ARCH-123", "specification": spec})
    decide(c, h["reviewer"], rejected["approval_id"], approve=False)
    assert post(c, f"/v1/meta/architecture/changes/{rejected['id']}/reconcile",
                h["founder"])["status"] == "rejected"
    post(c, "/v1/meta/architecture/changes", h["founder"],
         {"change_key": "ARCH-121", "specification": {**spec, "sections": [29]}}, expected=403)
    post(c, "/v1/meta/architecture/changes", h["reviewer"],
         {"change_key": "ARCH-122", "specification": spec}, expected=403)
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
        info["db"].execute("DELETE FROM ago_architecture_changes WHERE id=%s", (change["id"],))


def test_twenty_snapshot_reflection_has_bounded_warmed_latency(case):
    c, h, info = case
    for _ in range(20):
        post(c, "/v1/meta/snapshots", h["founder"])
    samples = []
    for _ in range(5):
        started = time.monotonic()
        result = c.get("/v1/meta/reflection", headers=h["founder"])
        assert result.status_code == 200, result.text
        assert result.json()["sample_count"] == 20
        samples.append(time.monotonic() - started)
    assert max(samples) < 3, f"Twenty-source reflection p95 regression: {samples}"


def test_reflection_observes_actual_independently_approved_company_brain_decision(case):
    c, h, info = case
    _, employee = team(c, h["founder"])
    goal = post(c, "/v1/brain/goals", h["founder"], {"title": "Evidence-based research"})
    plan = post(c, "/v1/brain/plans", h["founder"],
                {"goal_id": goal["id"], "title": "Reviewed internal brief"})
    post(c, f"/v1/brain/plans/{plan['id']}/steps", h["founder"],
         {"action": "internal:brief", "assignee_id": employee["id"]})
    pending = post(c, f"/v1/brain/plans/{plan['id']}/submit", h["founder"])
    decide(c, h["reviewer"], pending["approval_id"])
    post(c, f"/v1/brain/plans/{plan['id']}/activate", h["founder"])
    post(c, "/v1/meta/snapshots", h["founder"])
    post(c, "/v1/meta/snapshots", h["founder"])
    reflection = c.get("/v1/meta/reflection", headers=h["reviewer"]).json()
    decisions = reflection["decision_review"]["company_brain_decisions"]
    assert len(decisions) == 1
    assert decisions[0]["id"] == plan["id"]
    assert decisions[0]["status"] == "active"
    assert decisions[0]["approval_status"] == "approved"
    assert decisions[0]["reviewer_id"] == info["reviewer_id"]
    assert reflection["automatic_execution"] is False
