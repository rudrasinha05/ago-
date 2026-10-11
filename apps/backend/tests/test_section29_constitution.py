"""Highest policy acceptance over actual signed sessions, execution and PostgreSQL."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ago.governance_domain import (
    CONSTITUTION_CONTEXTS,
    CONSTITUTION_LAWS,
    constitutional_context,
    validate_constitution,
)
from ago.security import Principal
from ago.security_controls import SecurityControls
from test_m7_http_postgres import case as case, decide, post

BASE = "/v1/governance/constitution"


def package(simulation, blocked=None):
    return {
        "title": "Bounded company authority",
        "rationale": "Use the reviewed version to suspend specified operations",
        "risk": "Record missing real-world uncertainty; this is internal review",
        "affected_rights": "No grants expanded; human authority preserved",
        "alternatives": "Baseline authority and temporary containment considered",
        "dissent": "Simulation is descriptive; no external legal certification",
        "rollback": "New reviewed version restores operational contexts; no audit deletion",
        "monitoring": "Review denied-action audit and actual workflow outcomes",
        "propagation": "Central request and permission guards enforce policy above DNA",
        "blocked_contexts": blocked or [],
        "simulation_id": simulation,
    }


def simulation(client, founder):
    snap = post(client, "/v1/meta/snapshots", founder)
    return post(
        client,
        "/v1/operations/enterprise/twin",
        founder,
        {
            "snapshot_id": snap["id"],
            "actions": 1,
            "cost_per_action": "1",
            "budget": "10",
            "failure_pct": 0,
        },
    )["id"]


def propose(client, founder, sim, blocked=None, base=0, key=None):
    data = {
        "operation_key": key or str(uuid4()),
        "base_revision": base,
        "effective_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "specification": package(sim, blocked),
    }
    return post(client, BASE + "/proposals", founder, data), data


def emergency(client, founder, contexts=None, key=None):
    data = {
        "operation_key": key or str(uuid4()),
        "blocked_contexts": contexts or list(CONSTITUTION_CONTEXTS),
        "reason": "Disposable incident containment test",
        "containment": "Freeze business work; preserve review and evidence",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    return post(client, BASE + "/emergencies", founder, data), data


def test_laws_cannot_be_amended_and_recovery_remains_available():
    assert len(CONSTITUTION_LAWS) == 12
    for key in ["laws", "human_authority", "permissions", "disable_audit"]:
        with pytest.raises(ValueError, match="immutable"):
            validate_constitution({**package(str(uuid4())), key: False})
    for blocked in [["security"], ["constitution"], ["tools", "tools"], [{"area": "tools"}]]:
        with pytest.raises(ValueError):
            validate_constitution(package(str(uuid4()), blocked))
    assert constitutional_context("/v1/meta/dna") == "meta"
    assert constitutional_context("/v1/governance/constitution/adopt") is None
    assert constitutional_context("/v1/security/mfa/enroll") is None
    assert constitutional_context("/v1/unknown-operation") == "operations"


def test_amendment_full_package_all_five_reviews_and_exact_adoption(case):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    assert client.get(BASE).status_code == 401
    initial = client.get(BASE, headers=f).json()
    assert initial["active"]["revision"] == 0 and initial["human_authority"]
    sim = simulation(client, f)
    proposed, data = propose(client, f, sim, ["tools"])
    path = BASE + "/adopt"
    body = {"proposal_id": proposed["id"]}
    post(client, path, f, body, expected=403)
    post(client, BASE + "/proposals", r, data, expected=403)
    for domain, approval in proposed["reviews"].items():
        assert domain in initial["review_domains"]
        post(
            client,
            "/v1/governance/approvals/" + approval + "/decision",
            f,
            {"approve": True, "reason": "Forbidden"},
            expected=403,
        )
        decide(client, r, approval)
    result = post(client, path, f, body)
    assert result["revision"] == 1 and not result["idempotent"]
    assert post(client, path, f, body)["idempotent"]
    active = client.get(BASE, headers=r).json()
    assert active["active"]["revision"] == 1 and active["active"]["blocked_contexts"] == ["tools"]
    assert active["laws"] == initial["laws"]
    assert active["proposals"][0]["simulation"]["source_digest"]
    assert active["proposals"][0]["specification"]["propagation"]
    assert not SecurityControls(info["db"]).permitted(
        Principal(info["founder_id"], info["tenant"], ("founder",)), "tool:dispatch", info["tenant"]
    )
    assert SecurityControls(info["db"]).permitted(
        Principal(info["founder_id"], info["tenant"], ("founder",)), "tool:read", info["tenant"]
    )


def test_rejected_domain_stale_version_and_immutable_rows(case):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    sim = simulation(client, f)
    first, _ = propose(client, f, sim)
    rejected, _ = propose(client, f, sim, ["knowledge"])
    for approval in first["reviews"].values():
        decide(client, r, approval)
    for domain, approval in rejected["reviews"].items():
        decide(client, r, approval, approve=domain != "legal")
    post(client, BASE + "/adopt", f, {"proposal_id": rejected["id"]}, expected=403)
    post(client, BASE + "/adopt", f, {"proposal_id": first["id"]})
    for approval in rejected["reviews"].values():
        assert approval
    stale, _ = propose(client, f, sim, base=1)
    next_version, _ = propose(client, f, sim, base=1)
    for p in [stale, next_version]:
        for approval in p["reviews"].values():
            decide(client, r, approval)
    post(client, BASE + "/adopt", f, {"proposal_id": next_version["id"]})
    post(client, BASE + "/adopt", f, {"proposal_id": stale["id"]}, expected=403)
    psycopg = pytest.importorskip("psycopg")
    for table in ["ago_constitution_proposals", "ago_constitution_adoptions"]:
        with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
            info["db"].execute("DELETE FROM " + table + " WHERE tenant_id=%s", (info["tenant"],))


def test_emergency_covers_every_business_area_and_records_denials(case):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    incident, data = emergency(client, f)
    for area in CONSTITUTION_CONTEXTS:
        assert not SecurityControls(info["db"]).constitution_allowed(
            Principal(info["founder_id"], info["tenant"], ()), area
        )
    urls = [
        "/v1/organization/departments",
        "/v1/meta/snapshots",
        "/v1/tasks",
        "/v1/operations/enterprise/cycle",
        "/v1/brain/goals",
        "/v1/knowledge/nodes",
        "/v1/council/motions",
        "/v1/insights/budget",
        "/v1/tools/enrollments",
    ]
    # For an actual registered operation the common authentication guard runs before body/handler execution.
    routes = {path for path, methods in client.app.openapi()["paths"].items() if "post" in methods}
    for path in urls:
        if path in routes:
            post(client, path, f, {}, expected=403)
    assert client.get(BASE, headers=r).status_code == 200
    assert client.get("/v1/governance/approvals", headers=r).status_code == 200
    assert client.get("/v1/tasks", headers=f).status_code == 200
    denied = (
        info["db"]
        .execute(
            "SELECT metadata FROM ago_security_audit WHERE tenant_id=%s AND action='constitution:denied'",
            (info["tenant"],),
        )
        .fetchall()
    )
    assert len(denied) >= len(CONSTITUTION_CONTEXTS)
    assert post(client, BASE + "/emergencies", f, data)["idempotent"]
    post(client, BASE + "/emergencies", f, {**data, "operation_key": str(uuid4())}, expected=403)
    post(client, BASE + "/emergencies", f, {**data, "reason": "Changed retry"}, expected=403)
    state = client.get(BASE, headers=f).json()
    assert state["emergencies"][0]["id"] == incident["id"] and state["emergencies"][0]["active"]


def test_recovery_requires_independent_exact_postmortem_and_preserves_history(case):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    incident, _ = emergency(client, f, ["organization"])
    post(client, "/v1/organization/departments", f, {"name": "Frozen"}, expected=403)
    review = post(
        client,
        BASE + "/incident-review",
        f,
        {
            "emergency_id": incident["id"],
            "postmortem": "Root cause and containment inspected",
            "recovery_evidence": "Actual disposable service checks recovered",
        },
    )
    body = {"review_id": review["id"]}
    post(client, BASE + "/close-incident", f, body, expected=403)
    decide(client, r, review["approval_id"])
    assert post(client, BASE + "/close-incident", f, body)["closed"]
    assert post(client, BASE + "/close-incident", f, body)["idempotent"]
    post(client, "/v1/organization/departments", f, {"name": "Recovered"})
    state = client.get(BASE, headers=r).json()
    assert (
        not state["emergencies"][0]["active"]
        and not state["emergencies"][0]["retrospective_review_pending"]
    )
    assert state["emergency_reviews"][0]["postmortem"]
    psycopg = pytest.importorskip("psycopg")
    for table in [
        "ago_constitution_emergencies",
        "ago_constitution_emergency_reviews",
        "ago_constitution_emergency_closures",
    ]:
        with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
            info["db"].execute("DELETE FROM " + table + " WHERE tenant_id=%s", (info["tenant"],))


def test_foreign_missing_simulation_reviewer_revocation_and_unknown_authority(case):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    sim = simulation(client, f)
    bad = {
        "operation_key": "unknown-source",
        "base_revision": 0,
        "effective_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "specification": package(str(uuid4())),
    }
    post(client, BASE + "/proposals", f, bad, expected=404)
    post(
        client,
        BASE + "/proposals",
        f,
        {**bad, "specification": {**bad["specification"], "laws": {}}},
        expected=400,
    )
    post(client, BASE + "/proposals", f, {**bad, "base_revision": True}, expected=422)
    p, _ = propose(client, f, sim)
    for approval in p["reviews"].values():
        decide(client, r, approval)
    info["db"].execute(
        "UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["reviewer_id"]),
    )
    post(client, BASE + "/adopt", f, {"proposal_id": p["id"]}, expected=403)
    post(client, BASE + "/adopt", f, {"proposal_id": str(uuid4())}, expected=404)


def test_foreign_constitution_and_ai_founder_cannot_exercise_human_authority(case):
    from ago.bootstrap import bootstrap

    client, h, info = case
    f = h["founder"]
    sim = simulation(client, f)
    item, data = propose(client, f, sim)
    assert post(client, BASE + "/proposals", f, data)["idempotent"]
    post(
        client,
        BASE + "/proposals",
        f,
        {**data, "specification": {**data["specification"], "risk": "Changed package"}},
        expected=403,
    )
    tenant, _ = bootstrap(
        info["db"],
        organization="Foreign constitution",
        email="foreign@example.test",
        password="foreign-constitutional-password",
    )
    foreign = info["login"]("foreign@example.test", "foreign-constitutional-password", tenant)
    post(client, BASE + "/adopt", foreign, {"proposal_id": item["id"]}, expected=404)
    assert client.get(BASE, headers=foreign).json()["proposals"] == []
    info["db"].execute(
        "UPDATE ago_employees SET kind='ai' WHERE tenant_id=%s AND id=%s",
        (info["tenant"], info["founder_id"]),
    )
    post(
        client,
        BASE + "/emergencies",
        f,
        {
            "operation_key": "ai-emergency",
            "blocked_contexts": ["tools"],
            "reason": "AI cannot declare",
            "containment": "No authority granted",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        expected=403,
    )


def test_direct_adoption_cannot_bypass_reviews_and_expired_incident_still_needs_review(case):
    client, h, info = case
    f = h["founder"]
    sim = simulation(client, f)
    item, _ = propose(client, f, sim, ["tools"])
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), info["db"].transaction():
        info["db"].execute(
            """INSERT INTO ago_constitution_adoptions(id,tenant_id,proposal_id,actor_id,revision,blocked_contexts,effective_at)
               VALUES(%s,%s,%s,%s,1,ARRAY['tools'],clock_timestamp())""",
            (str(uuid4()), info["tenant"], item["id"], info["founder_id"]),
        )
    incident = str(uuid4())
    # Historical disposable fixture exercises actual clock expiry, rather than sleeping or altering history.
    info["db"].execute(
        """INSERT INTO ago_constitution_emergencies
           (id,tenant_id,actor_id,operation_key,blocked_contexts,reason,containment,digest,created_at,expires_at)
           VALUES(%s,%s,%s,'historical',ARRAY['tools'],'Expired test incident','Historical containment',%s,
                  clock_timestamp()-interval '2 hours',clock_timestamp()-interval '1 hour')""",
        (incident, info["tenant"], info["founder_id"], "a" * 64),
    )
    actor = Principal(info["founder_id"], info["tenant"], ())
    assert SecurityControls(info["db"]).constitution_allowed(actor, "tools")
    row = client.get(BASE, headers=f).json()["emergencies"][0]
    assert not row["active"] and row["retrospective_review_pending"]
    data = {
        "operation_key": "cannot-chain",
        "blocked_contexts": ["tools"],
        "reason": "Cannot avoid expired incident review",
        "containment": "Review previous incident",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    post(client, BASE + "/emergencies", f, data, expected=403)
    post(
        client,
        BASE + "/emergencies",
        f,
        {**data, "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()},
        expected=400,
    )
