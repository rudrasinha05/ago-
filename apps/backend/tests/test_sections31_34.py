"""Source-first enterprise batch: pure boundaries and actual PostgreSQL authority flows."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from ago.analytics_store import DASHBOARDS, anomaly, forecast_series
from ago.behavior_store import DIMENSIONS, summarize_signals
from ago.graph_store import NODE_KINDS, RELATIONS, node_spec
from ago.integration_store import redirect_uri, verify_webhook, webhook_signature, webhook_url
from ago.security import AuthenticationError
from test_enterprise_http_21_27 import department, employee
from test_enterprise_capacity_21 import _approved_task
from test_m7_http_postgres import case as case, decide, post

BASE = "/v1/enterprise"


def propose(client, f, domain, command, spec, **extra):
    revision = client.get(BASE + "/reviews/" + domain, headers=f).json()["revision"]
    data = {
        "command": command,
        "specification": spec,
        "operation_key": str(uuid4()),
        "base_revision": revision,
        "rationale": "Exact independently reviewed source and bounded authority",
    }
    data.update(extra)
    return post(client, BASE + "/reviews/" + domain + "/propose", f, data), data


def apply(client, f, r, domain, item):
    decide(client, r, item["approval_id"])
    return post(client, BASE + "/reviews/" + domain + "/apply", f, {"proposal_id": item["id"]})


def graph_node(owner, kind="project", **extra):
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid4()),
        "kind": kind,
        "label": "Reviewed project",
        "statement": "Observed source-backed entity",
        "owner_id": owner,
        "classification": "tenant",
        "readers": [],
        "source_ref": "document:verified-source",
        "source_at": now.isoformat(),
        "confidence": 0.8,
        "effective_at": now.isoformat(),
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "memory_ids": [],
        "legal_hold": False,
        **extra,
    }


def integration_client(subject, **extra):
    return {
        "id": str(uuid4()),
        "name": "Reviewed enterprise client",
        "type": "confidential",
        "subject_id": subject,
        "department_id": None,
        "scopes": ["events:read", "tasks:read", "tasks:propose"],
        "redirect_uris": [],
        "enabled": True,
        "requests_per_minute": 60,
        **extra,
    }


@pytest.mark.parametrize("kind", sorted(NODE_KINDS))
def test_all_enterprise_node_types_have_provenance(kind):
    assert node_spec(graph_node(str(uuid4()), kind))["kind"] == kind


@pytest.mark.parametrize(
    "bad",
    [
        {"confidence": True},
        {"confidence": float("nan")},
        {"confidence": 2},
        {"kind": "grant_permission"},
        {"classification": "public"},
        {"readers": [str(uuid4())] * 2},
        {"memory_ids": "all"},
        {"source_at": "2099-01-01T00:00:00Z"},
        {"effective_at": "2026-01-01"},
        {"legal_hold": "false"},
        {"statement": ""},
        {"protected_trait": "race"},
    ],
)
def test_graph_strict_schema_and_evidence_bounds(bad):
    with pytest.raises((ValueError, TypeError)):
        node_spec(graph_node(str(uuid4()), **bad))


def test_original_dimensions_and_relations_present():
    assert len(DIMENSIONS) == 13
    assert {
        "governed_by",
        "learned_from",
        "simulates",
        "uses_model",
        "has_skill",
        "caused_by",
    } <= RELATIONS
    assert len(DASHBOARDS) == 15


def test_behavior_sparse_stratified_uncertainty_and_drift():
    samples = [
        dict(
            dimension="reliability",
            scope="research",
            complexity="complex",
            risk="high",
            score=i / 10,
            observation_id=str(i),
        )
        for i in range(6)
    ]
    assert summarize_signals(samples[:4])[0]["score"] is None
    result = summarize_signals(samples)[0]
    assert (
        result["n"] == 6
        and result["score"] == 0.25
        and result["interval_95"][0] >= 0
        and result["drift_delta"] > 0
    )
    assert len(summarize_signals(samples + [{**samples[0], "risk": "low"}])) == 2


def test_forecasts_and_anomalies_do_not_invent_missing_evidence():
    now = datetime.now(timezone.utc)
    assert forecast_series([])["prediction"] is None
    assert forecast_series([(now, 1)] * 5)["status"] == "insufficient_time_span"
    p = [(now + timedelta(days=i), 10 + i * 2) for i in range(6)]
    result = forecast_series(p, 2)
    assert result["prediction"] == 24 and result["n"] == 6
    assert anomaly([10] * 6, 30)["flagged"]
    assert not anomaly([10] * 6, 11)["flagged"]
    assert anomaly([], 3)["status"] == "insufficient_evidence"


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example/hook",
        "https://localhost/h",
        "https://127.0.0.1/h",
        "https://169.254.169.254/h",
        "https://10.0.0.1/h",
        "https://user:pass@example.com/h",
        "https://example.com:444/h",
        "https://example.com/h#secret",
        "https://service.internal/h",
    ],
)
def test_webhook_ssrf_and_endpoint_validation(url):
    with pytest.raises(ValueError):
        webhook_url(url)


def test_webhook_hmac_expiry_tampering_and_persistent_replay(tmp_path):
    path = Path(__file__).resolve().parents[3] / "packages/sdk/python/ago_client.py"
    spec = importlib.util.spec_from_file_location("ago_client_sdk", path)
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    body = b'{"schema":"task.changed.v1","status":"ready"}'
    identifier = str(uuid4())
    secret = "s" * 40
    sig = webhook_signature(secret, 1000, identifier, body)
    assert verify_webhook(secret, 1000, identifier, body, sig, now=1001)
    for stamp, data in [(500, body), (1000, b"tampered")]:
        with pytest.raises(AuthenticationError):
            verify_webhook(secret, stamp, identifier, data, sig, now=1001)
    receiver = sdk.WebhookReceiver(str(tmp_path / "receipts.sqlite"))
    assert receiver.accept(secret, 1000, identifier, body, sig, now=1001)["status"] == "ready"
    receiver.db.close()
    receiver = sdk.WebhookReceiver(str(tmp_path / "receipts.sqlite"))
    with pytest.raises(ValueError, match="replay"):
        receiver.accept(secret, 1000, identifier, body, sig, now=1001)
    receiver.db.close()
    assert redirect_uri("http://127.0.0.1:9999/callback")
    with pytest.raises(ValueError):
        redirect_uri("http://external.example/callback")


def test_graph_review_version_merge_delete_and_typed_paths(case):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    owner = info["founder_id"]
    node = graph_node(owner, "employee")
    item, data = propose(c, f, "graph", "node", node)
    assert post(c, BASE + "/reviews/graph/propose", f, data)["id"] == item["id"]
    post(c, BASE + "/reviews/graph/propose", f, {**data, "rationale": "changed"}, expected=403)
    post(c, BASE + "/reviews/graph/apply", f, {"proposal_id": item["id"]}, expected=403)
    post(
        c,
        "/v1/governance/approvals/" + item["approval_id"] + "/decision",
        f,
        {"approve": True, "reason": "self"},
        expected=403,
    )
    assert (
        c.get(BASE + "/reviews/source/" + item["approval_id"], headers=r).json()["digest"]
        == item["digest"]
    )
    apply(c, f, r, "graph", item)
    skill = graph_node(owner, "skill")
    item, _ = propose(c, f, "graph", "node", skill)
    apply(c, f, r, "graph", item)
    edge = {
        "id": str(uuid4()),
        "from_id": node["id"],
        "to_id": skill["id"],
        "relation": "has_skill",
        "source_ref": "reviewed skills record",
        "confidence": 0.8,
        "inferred": False,
        "expires_at": skill["expires_at"],
    }
    item, _ = propose(c, f, "graph", "edge", edge)
    apply(c, f, r, "graph", item)
    graph = c.get(
        BASE + "/graph", headers=f, params={"root_id": node["id"], "direction": "out"}
    ).json()
    assert graph["paths"][skill["id"]] == [node["id"], skill["id"]]
    assert len(graph["edges"]) == 1
    quality = c.get(BASE + "/graph/quality", headers=f).json()
    assert quality["visible_nodes"] == 2
    replacement = graph_node(owner, "skill")
    item, _ = propose(c, f, "graph", "node", replacement)
    apply(c, f, r, "graph", item)
    item, _ = propose(
        c,
        f,
        "graph",
        "merge",
        {"id": skill["id"], "target_id": replacement["id"], "reason": "Verified duplicate"},
    )
    apply(c, f, r, "graph", item)
    assert c.get(BASE + "/graph", headers=f, params={"root_id": skill["id"]}).status_code == 404
    graph = c.get(BASE + "/graph", headers=f, params={"root_id": node["id"]}).json()
    assert graph["edges"][0]["payload"]["to_id"] == replacement["id"]
    item, _ = propose(
        c, f, "graph", "delete", {"id": replacement["id"], "reason": "Reviewed retirement"}
    )
    apply(c, f, r, "graph", item)
    assert not c.get(BASE + "/graph", headers=f, params={"root_id": node["id"]}).json()["edges"]


def test_graph_restricted_legal_hold_and_foreign_source_fail_closed(case):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    node = graph_node(info["founder_id"], "document", classification="restricted", legal_hold=True)
    item, _ = propose(c, f, "graph", "node", node)
    apply(c, f, r, "graph", item)
    assert c.get(BASE + "/graph", headers=r).json()["nodes"] == []
    assert c.get(BASE + "/graph", headers=r, params={"root_id": node["id"]}).status_code == 404
    revision = c.get(BASE + "/reviews/graph", headers=f).json()["revision"]
    post(
        c,
        BASE + "/reviews/graph/propose",
        f,
        dict(
            command="delete",
            specification={"id": node["id"], "reason": "remove"},
            operation_key=str(uuid4()),
            base_revision=revision,
            rationale="Cannot override hold",
        ),
        expected=403,
    )
    post(
        c,
        BASE + "/reviews/graph/propose",
        f,
        dict(
            command="node",
            specification=graph_node(str(uuid4())),
            operation_key=str(uuid4()),
            base_revision=revision,
            rationale="Foreign owner",
        ),
        expected=403,
    )


def test_behavior_review_source_privacy_expiry_appeal_and_hr_gate(case):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    worker = employee(c, f, department(c, f))
    definition = {
        "id": str(uuid4()),
        "dimension": "reliability",
        "name": "Correct bounded output",
        "rubric": "1 means independent QA pass;0 means fail",
        "limitations": "Not normalized across task risk",
        "minimum_samples": 5,
        "version": 1,
    }
    item, _ = propose(c, f, "behavior", "definition", definition)
    apply(c, f, r, "behavior", item)
    task = _approved_task(c, f, r, worker)
    post(c, "/v1/agents/tasks/" + task + "/run", f, {})
    post(
        c,
        "/v1/tasks/" + task + "/review",
        r,
        {"verdict": "pass", "evidence": "Independently checked source output"},
    )
    observation = {
        "id": str(uuid4()),
        "employee_id": worker,
        "definition_id": definition["id"],
        "task_id": task,
        "dimension": "reliability",
        "scope": "research",
        "complexity": "routine",
        "risk": "low",
        "score": 1,
        "rationale": "Actual QA result",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    item, _ = propose(c, f, "behavior", "observation", observation)
    apply(c, f, r, "behavior", item)
    profile = c.get(BASE + "/behavior/" + worker, headers=f).json()
    assert (
        profile["signals"][0]["score"] is None
        and profile["validation"]["reviewed_observations"] == 1
    )
    appeal = post(
        c,
        BASE + "/behavior/" + worker + "/appeals",
        r,
        {"reason": "Scoring ignored task complexity"},
    )
    from ago.behavior_store import BehaviorStore
    from ago.security import Principal

    with pytest.raises(PermissionError):
        BehaviorStore(info["db"]).require_clear(
            actor=Principal(info["founder_id"], info["tenant"], ("founder",)), employee_id=worker
        )
    resolution = {
        "id": str(uuid4()),
        "employee_id": worker,
        "appeal_id": appeal["id"],
        "resolution": "corrected",
        "excluded_observation_ids": [observation["id"]],
        "rationale": "Exclude disputed source after independent review",
    }
    item, _ = propose(c, f, "behavior", "resolve_appeal", resolution)
    apply(c, f, r, "behavior", item)
    profile = c.get(BASE + "/behavior/" + worker, headers=f).json()
    assert profile["signals"] == [] and profile["open_appeals"] == []
    assert c.get(BASE + "/behavior/" + info["founder_id"], headers=f).status_code == 403


def test_all_analytics_dashboards_lineage_snapshot_schedules_and_unknowns(case):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    dept = department(c, f)
    worker = employee(c, f, dept)
    for name in DASHBOARDS:
        result = c.get(
            BASE + "/analytics/dashboard",
            headers=f,
            params={"dashboard": name, "department_id": dept, "employee_id": worker},
        )
        assert result.status_code == 200, result.text
        data = result.json()
        assert data["dashboard"] == name and data["definition_version"] == 1
        assert all("source" in x and "limitations" in x for x in data["metrics"].values())
    first = post(c, BASE + "/analytics/snapshots", f, {"operation_key": "stable-snapshot"})
    assert (
        post(c, BASE + "/analytics/snapshots", f, {"operation_key": "stable-snapshot"})["id"]
        == first["id"]
    )
    assert (
        c.get(BASE + "/analytics/history/backlog", headers=f).json()["forecast"]["prediction"]
        is None
    )
    schedule = {"id": str(uuid4()), "report": "executive", "cadence": "weekly", "enabled": True}
    item, _ = propose(c, f, "analytics", "schedule", schedule)
    apply(c, f, r, "analytics", item)
    assert len(post(c, BASE + "/analytics/tick", f, {})["created_report_ids"]) == 1
    assert not post(c, BASE + "/analytics/tick", f, {})["created_report_ids"]
    assert len(c.get(BASE + "/analytics/reports", headers=f).json()) == 1


def test_integration_key_scopes_idempotency_events_and_revocation(case):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    dept = department(c, f)
    worker = employee(c, f, dept)
    client = integration_client(info["founder_id"], department_id=dept)
    item, _ = propose(c, f, "integration", "client", client)
    apply(c, f, r, "integration", item)
    credential = post(
        c, "/v1/platform/clients/" + client["id"] + "/credentials", f, {"kind": "api_key"}
    )
    auth = {"Authorization": "Bearer " + credential["credential"], "Idempotency-Key": "task-once"}
    task = post(c, "/v1/platform/tasks", auth, {"action": "internal:brief", "assignee_id": worker})
    assert task["status"] == "proposed"
    assert (
        post(c, "/v1/platform/tasks", auth, {"action": "internal:brief", "assignee_id": worker})[
            "id"
        ]
        == task["id"]
    )
    post(
        c,
        "/v1/platform/tasks",
        auth,
        {"action": "internal:other", "assignee_id": worker},
        expected=403,
    )
    assert c.get("/v1/tasks", headers=auth).status_code == 401
    post(c, "/v1/platform/publish", f, {})
    events = c.get("/v1/platform/events", headers=auth).json()
    assert len(events["events"]) == 1
    assert "action" not in events["events"][0]["payload"]
    assert len(c.get("/v1/platform/tasks", headers=auth).json()["tasks"]) == 1
    assert (
        c.get("/v1/platform/events", headers=auth, params={"after": events["next_cursor"]}).json()[
            "events"
        ]
        == []
    )
    client["enabled"] = False
    item, _ = propose(c, f, "integration", "client", client)
    apply(c, f, r, "integration", item)
    assert c.get("/v1/platform/events", headers=auth).status_code == 401


def test_oauth_confidential_and_public_pkce_replay(case):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    client = integration_client(info["founder_id"])
    item, _ = propose(c, f, "integration", "client", client)
    apply(c, f, r, "integration", item)
    secret = post(
        c, "/v1/platform/clients/" + client["id"] + "/credentials", f, {"kind": "client_secret"}
    )["credential"]
    token = c.post(
        "/v1/platform/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client["id"],
            "client_secret": secret,
            "scope": "events:read",
        },
    )
    assert token.status_code == 200, token.text
    assert token.json()["expires_in"] == 300 and token.headers["cache-control"] == "no-store"
    auth = {"Authorization": "Bearer " + token.json()["access_token"]}
    post(
        c,
        "/v1/platform/tasks",
        auth,
        {"action": "internal:brief", "assignee_id": info["founder_id"]},
        expected=403,
    )
    public = integration_client(
        info["founder_id"], type="public", redirect_uris=["http://127.0.0.1:7777/cb"]
    )
    item, _ = propose(c, f, "integration", "client", public)
    apply(c, f, r, "integration", item)
    verifier = "v" * 50
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    grant = post(
        c,
        "/v1/platform/oauth/authorize",
        f,
        {
            "client_id": public["id"],
            "redirect_uri": public["redirect_uris"][0],
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scopes": ["events:read"],
            "state": "random-client-state-123",
        },
    )
    data = {
        "grant_type": "authorization_code",
        "client_id": public["id"],
        "code": grant["code"],
        "redirect_uri": public["redirect_uris"][0],
        "code_verifier": verifier,
    }
    assert (
        c.post("/v1/platform/oauth/token", data={**data, "code_verifier": "wrong" * 10}).status_code
        == 401
    )
    response = c.post("/v1/platform/oauth/token", data=data)
    assert response.status_code == 200, response.text
    assert c.post("/v1/platform/oauth/token", data=data).status_code == 401


def test_webhook_retry_rotation_and_plugin_lifecycle(case, monkeypatch):
    c, h, info = case
    f, r = h["founder"], h["reviewer"]
    client = integration_client(info["founder_id"])
    item, _ = propose(c, f, "integration", "client", client)
    apply(c, f, r, "integration", item)
    sub = {
        "id": str(uuid4()),
        "client_id": client["id"],
        "url": "https://receiver.example/ago",
        "event_types": ["task.changed.v1"],
        "enabled": True,
    }
    item, _ = propose(c, f, "integration", "webhook", sub)
    apply(c, f, r, "integration", item)
    monkeypatch.setenv(
        "AGO_MFA_KEYS",
        json.dumps(
            {"current": "test", "keys": {"test": base64.urlsafe_b64encode(b"k" * 32).decode()}}
        ),
    )
    key = post(c, "/v1/platform/webhooks/" + sub["id"] + "/rotate", f, {})
    worker = employee(c, f, department(c, f))
    _approved_task(c, f, r, worker)
    post(c, "/v1/platform/publish", f, {})
    received = []

    def send(url, body, headers):
        assert verify_webhook(
            key["secret"],
            int(headers["X-AGO-Timestamp"]),
            headers["X-AGO-Delivery"],
            body,
            headers["X-AGO-Signature"],
        )
        received.append(body)
        return 503 if len(received) == 1 else 204

    monkeypatch.setattr("ago.integration_store.deliver_https", send)
    post(c, "/v1/platform/webhooks/deliver", f, {}, expected=403)
    monkeypatch.setenv("AGO_WEBHOOK_DELIVERY_ENABLED", "true")
    result = post(c, "/v1/platform/webhooks/deliver", f, {})["deliveries"][0]
    assert result["status"] == "retry"
    info["db"].execute(
        "UPDATE ago_webhook_deliveries SET next_attempt_at=clock_timestamp()-interval '1 second' WHERE tenant_id=%s",
        (info["tenant"],),
    )
    assert post(c, "/v1/platform/webhooks/deliver", f, {})["deliveries"][0]["status"] == "delivered"
    plugin = {
        "id": str(uuid4()),
        "client_id": client["id"],
        "name": "Research connector",
        "version": "1.0.0",
        "extension": "connector",
        "state": "installed",
        "manifest_sha256": "a" * 64,
        "permissions": ["tasks:read"],
        "configuration": {},
    }
    for state in ("installed", "configured", "enabled", "disabled", "deprecated", "removed"):
        plugin["state"] = state
        item, _ = propose(c, f, "integration", "plugin", plugin)
        apply(c, f, r, "integration", item)
