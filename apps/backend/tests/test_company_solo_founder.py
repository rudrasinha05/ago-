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
