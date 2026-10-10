"""M8 authenticated, isolated PostgreSQL integration for enterprise tools."""
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
        pytest.skip("Migrated PostgreSQL integration database required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    monkeypatch.setenv("AGO_SESSION_SECRET", "m8-signed-session-integration-key-123456789")
    monkeypatch.delenv("AGO_M8_EXTERNAL_ENABLED", raising=False)
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, founder_id = bootstrap(
                db, organization="M8 Secure Enterprise",
                email="m8founder@example.test", password="founder-password-123",
            )
            reviewer_id = add_reviewer(
                db, tenant_id=tenant,
                email="m8reviewer@example.test", password="reviewer-password-123",
            )
            app = create_app()
            app.dependency_overrides[api_m2.db_connection] = lambda: db
            with TestClient(app) as client:
                def login(email, password, tenant_id=tenant):
                    result = client.post("/v1/sessions", json={
                        "tenant_id": tenant_id, "email": email, "password": password,
                    })
                    assert result.status_code == 200, result.text
                    return {"Authorization": "Bearer " + result.json()["access_token"]}
                headers = {
                    "founder": login("m8founder@example.test", "founder-password-123"),
                    "reviewer": login("m8reviewer@example.test", "reviewer-password-123"),
                }
                yield client, headers, {
                    "db": db, "tenant": tenant,
                    "founder_id": founder_id, "reviewer_id": reviewer_id,
                    "login": login,
                }
        finally:
            db.rollback()


def post(client, url, headers, data=None, expected=200):
    result = client.post(url, headers=headers, json=data or {})
    assert result.status_code == expected, (url, result.status_code, result.text)
    return result.json()


def decision(client, reviewer, approval_id, *, approve=True):
    return post(
        client, f"/v1/governance/approvals/{approval_id}/decision",
        reviewer, {"approve": approve, "reason": "Independent human tool authorization"},
    )


def enroll(client, founder, reviewer, code):
    item = post(client, "/v1/tools/enrollments", founder, {
        "code": code, "rationale": "Enable a specific read-only tool after review",
    })
    decision(client, reviewer, item["approval_id"])
    assert post(
        client, f"/v1/tools/enrollments/{item['id']}/reconcile", founder,
    )["status"] == "active"
    return item


def create_ai(client, founder):
    departments = client.get(
        "/v1/organization/departments", headers=founder,
    ).json()
    assert departments
    employee = post(client, "/v1/organization/employees", founder, {
        "department_id": departments[0]["id"],
        "name": "Enterprise Tool Worker", "kind": "ai",
    })
    return departments[0]["id"], employee["id"]


def verified_node(client, founder, reviewer):
    node = post(client, "/v1/knowledge/nodes", founder, {
        "kind": "fact", "label": "M8 verified knowledge",
        "statement": "The source was independently checked",
        "source_ref": "internal:evidence:m8-fixture",
    })
    post(client, f"/v1/knowledge/nodes/{node['id']}/review", reviewer, {
        "approve": True, "note": "Reviewed M8 evidence",
    })
    return node["id"]


def test_verified_department_trigger_requires_separate_task_review(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    assert client.get("/v1/tools/catalog").status_code == 401
    assert client.get("/v1/tools/catalog", headers=reviewer).status_code == 200
    enrollment = post(client, "/v1/tools/enrollments", founder, {
        "code": "tool:knowledge_digest",
        "rationale": "Restricted knowledge report for reviewed department workflow",
    })
    post(client, f"/v1/tools/enrollments/{enrollment['id']}/reconcile",
         founder, expected=403)
    post(client, f"/v1/governance/approvals/{enrollment['approval_id']}/decision",
         founder, {"approve": True, "reason": "Self review"}, expected=403)
    decision(client, reviewer, enrollment["approval_id"])
    post(client, f"/v1/tools/enrollments/{enrollment['id']}/reconcile", founder)
    department_id, employee_id = create_ai(client, founder)
    rule = post(client, "/v1/tools/automation/rules", founder, {
        "department_id": department_id, "assignee_id": employee_id,
        "code": "tool:knowledge_digest", "trigger": "knowledge_verified",
    })
    source_id = verified_node(client, founder, reviewer)
    fire_url = f"/v1/tools/automation/rules/{rule['id']}/fire"
    fired = post(client, fire_url, founder, {"source_id": source_id})
    assert fired["created"] is True
    assert fired["execution_permitted"] is False
    again = post(client, fire_url, founder, {"source_id": source_id})
    assert again["created"] is False and again["task_id"] == fired["task_id"]
    assert client.post("/v1/tools/automation/scan", headers=founder,
                       json={"limit": 10}).json()["firings"] == []
    run_url = f"/v1/tools/tasks/{fired['task_id']}/run"
    post(client, run_url, founder, expected=403)
    decision(client, reviewer, fired["approval_id"])
    result = post(client, run_url, founder)
    assert result["status"] == "completed"
    assert result["requires_independent_qa"] is True
    assert result["result"]["verified"] >= 1
    post(client, run_url, founder, expected=403)
    logs = client.get(f"/v1/tools/runs/{result['id']}/evidence",
                      headers=founder)
    assert logs.status_code == 200
    assert [item["event"] for item in logs.json()] == ["claimed", "completed"]
    post(client, f"/v1/tasks/{fired['task_id']}/review", reviewer, {
        "verdict": "pass", "evidence": "Verified delivered digest",
    })
    score = client.get("/v1/insights/scorecard", headers=founder)
    assert score.status_code == 200
    assert score.json()["counts"]["tool_runs"] == 1
    assert score.json()["counts"]["automation_firings"] == 1


def test_pending_rejected_and_disabled_tool_enrollments_fail_closed(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept, ai = create_ai(client, founder)
    task = post(client, "/v1/tasks", founder, {
        "assignee_id": ai, "action": "tool:scorecard",
    })
    approval = post(client, "/v1/governance/approvals", founder, {
        "action": "tool:scorecard",
    })
    post(client, f"/v1/tasks/{task['id']}/approval", founder, {
        "approval_id": approval["request_id"],
    })
    decision(client, reviewer, approval["request_id"])
    run_url = f"/v1/tools/tasks/{task['id']}/run"
    post(client, run_url, founder, expected=403)
    proposed = post(client, "/v1/tools/enrollments", founder, {
        "code": "tool:scorecard", "rationale": "Read-only business report",
    })
    post(client, run_url, founder, expected=403)
    decision(client, reviewer, proposed["approval_id"], approve=False)
    assert post(client, f"/v1/tools/enrollments/{proposed['id']}/reconcile",
                founder)["status"] == "rejected"
    post(client, run_url, founder, expected=403)
    enabled = enroll(client, founder, reviewer, "tool:scorecard")
    result = post(client, run_url, founder)
    assert result["result"]["kind"] == "tenant_scorecard"
    assert result["result"]["data"]["counts"]["tool_runs"] == 1
    disabled = post(client, f"/v1/tools/enrollments/{enabled['id']}/disable",
                    founder, {"reason": "Operator disabled after review"})
    assert disabled["status"] == "disabled"
    post(client, f"/v1/tools/enrollments/{enabled['id']}/disable", founder,
         {"reason": "Duplicate disable"}, expected=403)
    assert client.post("/v1/tools/enrollments", headers=reviewer,
                       json={"code": "tool:scorecard",
                             "rationale": "Unauthorized"}).status_code == 403
    assert client.get("/v1/tools/runs", headers=reviewer).status_code == 200


def test_cross_tenant_cannot_read_or_claim_foreign_tool_activity(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    enrollment = enroll(client, founder, reviewer, "tool:knowledge_digest")
    from ago.bootstrap import bootstrap as new_tenant
    another, _ = new_tenant(
        info["db"], organization=f"Separate-M8-{uuid4()}",
        email="outside@m8.test", password="outside-password-123",
    )
    outsider = info["login"]("outside@m8.test", "outside-password-123", another)
    assert client.get("/v1/tools/enrollments", headers=outsider).json() == []
    assert client.get("/v1/tools/runs", headers=outsider).json() == []
    assert client.get("/v1/tools/automation/rules", headers=outsider).json() == []
    post(client, f"/v1/tools/enrollments/{enrollment['id']}/disable",
         outsider, {"reason": "Unauthorized"}, expected=404)
