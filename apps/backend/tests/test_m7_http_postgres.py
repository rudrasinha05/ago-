"""M7 real-session, PostgreSQL-isolated Meta Brain and DNA acceptance flows."""
from uuid import uuid4
import os

import pytest
from fastapi.testclient import TestClient

from ago import api_m2
from ago.bootstrap import bootstrap
from ago.main import create_app
from ago.provision import add_reviewer


@pytest.fixture
def case(monkeypatch):
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Migrated disposable PostgreSQL test DB is required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    monkeypatch.setenv("AGO_SESSION_SECRET", "m7-integration-test-signing-secret-123456789")
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, founder_id = bootstrap(
                db, organization="M7 Research Governance",
                email="m7founder@example.test", password="founder-test-password-123",
            )
            reviewer_id = add_reviewer(
                db, tenant_id=tenant, email="m7reviewer@example.test",
                password="reviewer-test-password-123",
            )
            app = create_app()
            app.dependency_overrides[api_m2.db_connection] = lambda: db
            with TestClient(app) as client:
                def login(email, password, identity=tenant):
                    response = client.post(
                        "/v1/sessions",
                        json={
                            "tenant_id": identity, "email": email,
                            "password": password,
                        },
                    )
                    assert response.status_code == 200, response.text
                    return {
                        "Authorization": "Bearer " + response.json()["access_token"],
                    }

                headers = {
                    "founder": login("m7founder@example.test", "founder-test-password-123"),
                    "reviewer": login("m7reviewer@example.test", "reviewer-test-password-123"),
                }
                yield client, headers, {
                    "db": db, "tenant": tenant,
                    "founder_id": founder_id, "reviewer_id": reviewer_id,
                    "login": login,
                }
        finally:
            db.rollback()


def post(client, path, headers, data=None, expected=200):
    response = client.post(path, json=data or {}, headers=headers)
    assert response.status_code == expected, (path, response.status_code, response.text)
    return response.json()


def profile(*, backlog_limit=5, qa_target_pct=85, budget_alert_pct=80):
    return {
        "qa_target_pct": qa_target_pct,
        "backlog_limit": backlog_limit,
        "budget_alert_pct": budget_alert_pct,
    }


def decide(client, reviewer, approval_id, *, approve=True):
    return post(
        client, f"/v1/governance/approvals/{approval_id}/decision",
        reviewer, {"approve": approve, "reason": "Independent human governance review"},
    )


def test_dna_requires_independent_approval_and_versions_are_immutable(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    assert client.get("/v1/meta/dna/active").status_code == 401
    baseline = client.get("/v1/meta/dna/active", headers=founder)
    assert baseline.status_code == 200
    assert baseline.json()["source"] == "baseline"
    assert baseline.json()["id"] is None
    candidate = post(client, "/v1/meta/dna", founder, {
        "profile": profile(backlog_limit=0),
        "rationale": "Pilot stricter backlog monitoring.",
    })
    assert candidate["version"] == 1
    post(client, f"/v1/meta/dna/{candidate['id']}/reconcile", founder, expected=403)
    post(client, f"/v1/governance/approvals/{candidate['approval_id']}/decision",
         founder, {"approve": True, "reason": "Self-review forbidden"}, expected=403)
    decide(client, reviewer, candidate["approval_id"])
    assert post(client, f"/v1/meta/dna/{candidate['id']}/reconcile", founder) == {
        "id": candidate["id"], "version": 1, "status": "active",
    }
    assert client.get("/v1/meta/dna/active", headers=founder).json()["profile"] == (
        profile(backlog_limit=0)
    )
    post(client, f"/v1/meta/dna/{candidate['id']}/reconcile", founder, expected=403)
    second = post(client, "/v1/meta/dna", founder, {
        "profile": profile(backlog_limit=3, qa_target_pct=90),
        "rationale": "Make the next evaluated DNA version stricter.",
    })
    assert second["version"] == 2
    decide(client, reviewer, second["approval_id"])
    post(client, f"/v1/meta/dna/{second['id']}/reconcile", founder)
    versions = client.get("/v1/meta/dna", headers=founder).json()
    assert [version["status"] for version in versions] == ["active", "superseded"]
    assert client.get("/v1/meta/dna/active", headers=reviewer).status_code == 200
    assert client.post("/v1/meta/dna", json={"profile": profile(),
                       "rationale": "Unauthorized"}, headers=reviewer).status_code == 403
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                "UPDATE ago_dna_versions SET rationale='rewritten' WHERE id=%s",
                (second["id"],),
            )


def test_snapshot_and_meta_brain_advice_require_separate_human_endorsement(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    assert client.get("/v1/meta/brief", headers=founder).json()["status"] == (
        "needs_snapshot"
    )
    snapshot = post(client, "/v1/meta/snapshots", founder)
    assert snapshot["fitness"] is None
    assert snapshot["risk_flags"] == ["insufficient_data"]
    assert len(snapshot["digest"]) == 64
    assert snapshot["recorded"]
    assert client.post("/v1/meta/snapshots", headers=reviewer).status_code == 403
    simulation = post(client, "/v1/meta/simulate", founder, {
        "snapshot_id": snapshot["id"], "profile": profile(backlog_limit=0),
    })
    assert simulation["applied"] is False
    assert simulation["source_digest"] == snapshot["digest"]
    assert simulation["assessment"]["fitness"] is None
    url = f"/v1/meta/snapshots/{snapshot['id']}/recommendations"
    first = post(client, url, founder)
    second = post(client, url, founder)
    assert len(first) == len(second) == 1
    assert first[0]["id"] == second[0]["id"]
    assert first[0]["category"] == "insufficient_data"
    assert first[0]["evidence"]["snapshot_digest"] == snapshot["digest"]
    recommendation = first[0]
    reconcile = f"/v1/meta/recommendations/{recommendation['id']}/reconcile"
    post(client, reconcile, founder, expected=403)
    post(client,
         f"/v1/governance/approvals/{recommendation['approval_id']}/decision",
         founder, {"approve": True, "reason": "Self endorsement"}, expected=403)
    decide(client, reviewer, recommendation["approval_id"])
    concluded = post(client, reconcile, founder)
    assert concluded["status"] == "endorsed" and concluded["executed"] is False
    post(client, reconcile, founder, expected=403)
    brief = client.get("/v1/meta/brief", headers=founder)
    assert brief.status_code == 200, brief.text
    assert brief.json()["advisory_only"] is True
    assert brief.json()["automatic_execution"] is False
    assert brief.json()["recommendations"][0]["status"] == "endorsed"
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                "UPDATE ago_executive_snapshots SET digest=%s WHERE id=%s",
                ("0" * 64, snapshot["id"]),
            )
    with pytest.raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                "UPDATE ago_meta_recommendations SET summary=%s WHERE id=%s",
                ("unreviewed change", recommendation["id"]),
            )


def test_meta_brain_detects_real_backlog_qa_and_budget_risk(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dna = post(client, "/v1/meta/dna", founder, {
        "profile": profile(backlog_limit=0),
        "rationale": "Evaluate task quality and credit consumption.",
    })
    decide(client, reviewer, dna["approval_id"])
    post(client, f"/v1/meta/dna/{dna['id']}/reconcile", founder)
    departments = client.get(
        "/v1/organization/departments", headers=founder,
    ).json()
    agent = post(client, "/v1/organization/employees", founder, {
        "department_id": departments[0]["id"], "name": "Meta Research AI",
        "kind": "ai",
    })
    finished = post(client, "/v1/tasks", founder, {
        "assignee_id": agent["id"], "action": "internal:brief",
    })
    post(client, "/v1/tasks", founder, {
        "assignee_id": agent["id"], "action": "internal:brief",
    })
    approval = post(client, "/v1/governance/approvals", founder, {
        "action": "internal:brief",
    })
    post(client, f"/v1/tasks/{finished['id']}/approval", founder, {
        "approval_id": approval["request_id"],
    })
    decide(client, reviewer, approval["request_id"])
    assert post(
        client, f"/v1/agents/tasks/{finished['id']}/run", founder,
    )["status"] == "completed"
    post(client, "/v1/insights/budget", founder, {"ceiling": "10"})
    post(client, "/v1/insights/usage", founder, {
        "operation_key": "m7-evidence-charge", "amount": "9",
        "category": "model_eval",
    })
    snapshot = post(client, "/v1/meta/snapshots", founder)
    assert snapshot["dna_id"] == dna["id"]
    assert snapshot["metrics"]["completed_tasks"] == 1
    assert snapshot["metrics"]["total_tasks"] == 2
    assert snapshot["metrics"]["qa_pass"] == 0
    assert snapshot["metrics"]["backlog_tasks"] == 1
    assert snapshot["metrics"]["budget_configured"] is True
    assert snapshot["fitness"] == "19.50"
    assert set(snapshot["risk_flags"]) == {
        "qa_below_target", "backlog_over_limit", "budget_alert",
    }
    hypothetical = post(client, "/v1/meta/simulate", founder, {
        "snapshot_id": snapshot["id"],
        "profile": profile(backlog_limit=5, budget_alert_pct=95),
    })
    assert hypothetical["assessment"]["risk_flags"] == ["qa_below_target"]
    assert hypothetical["assessment"]["fitness"] == snapshot["fitness"]
    recommendations = post(
        client, f"/v1/meta/snapshots/{snapshot['id']}/recommendations",
        founder,
    )
    assert len(recommendations) == 3
    assert {r["category"] for r in recommendations} == set(snapshot["risk_flags"])


def test_cross_tenant_evidence_isolation_and_immediate_rbac_revocation(case):
    from ago.bootstrap import bootstrap as new_tenant
    from ago.security_controls import SecurityControls

    client, headers, info = case
    source = post(client, "/v1/meta/snapshots", headers["founder"])
    other, _ = new_tenant(
        info["db"], organization=f"Other-{uuid4()}",
        email="outsider@example.test", password="outsider-password-123",
    )
    outsider = info["login"](
        "outsider@example.test", "outsider-password-123", other,
    )
    assert client.get("/v1/meta/snapshots", headers=outsider).json() == []
    assert client.get(
        f"/v1/meta/snapshots/{source['id']}", headers=outsider,
    ).status_code == 404
    post(client, f"/v1/meta/snapshots/{source['id']}/recommendations",
         outsider, expected=404)
    assert client.get("/v1/meta/brief", headers=outsider).json()["status"] == (
        "needs_snapshot"
    )
    SecurityControls(info["db"]).revoke_grant(
        info["tenant"], "founder", "meta:observe",
    )
    post(client, "/v1/meta/snapshots", headers["founder"], expected=403)


def test_rejected_dna_cannot_be_activated(case):
    client, headers, info = case
    candidate = post(client, "/v1/meta/dna", headers["founder"], {
        "profile": profile(),
        "rationale": "Not automatically allowed to alter team operating thresholds.",
    })
    decide(client, headers["reviewer"], candidate["approval_id"], approve=False)
    rejected = post(
        client, f"/v1/meta/dna/{candidate['id']}/reconcile",
        headers["founder"],
    )
    assert rejected["status"] == "rejected"
    assert client.get("/v1/meta/dna/active", headers=headers["founder"]).json()[
        "source"
    ] == "baseline"
    post(client, f"/v1/meta/dna/{candidate['id']}/reconcile",
         headers["founder"], expected=403)
    invalid = client.post("/v1/meta/dna", headers=headers["founder"], json={
        "profile": {**profile(), "disable_governance": True},
        "rationale": "Unknown key",
    })
    assert invalid.status_code == 422
