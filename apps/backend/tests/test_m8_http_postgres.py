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


def test_handler_failure_is_a_terminal_record_not_a_silent_retry(case, monkeypatch):
    import ago.tool_runtime as runtime_module

    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    enroll(client, founder, reviewer, "tool:scorecard")
    _, employee = create_ai(client, founder)
    task = post(client, "/v1/tasks", founder, {
        "action": "tool:scorecard", "assignee_id": employee,
    })
    approval = post(client, "/v1/governance/approvals", founder, {
        "action": "tool:scorecard",
    })
    post(client, f"/v1/tasks/{task['id']}/approval", founder, {
        "approval_id": approval["request_id"],
    })
    decision(client, reviewer, approval["request_id"])

    def fail(_task):
        raise RuntimeError("provider token should never be exposed")

    monkeypatch.setattr(
        runtime_module, "handlers", lambda _db: {"tool:scorecard": fail},
    )
    url = f"/v1/tools/tasks/{task['id']}/run"
    response = client.post(url, headers=founder)
    assert response.status_code == 502
    assert "provider token" not in response.text
    post(client, url, founder, expected=403)
    runs = client.get("/v1/tools/runs", headers=founder)
    assert runs.status_code == 200
    assert runs.json()[0]["status"] == "failed"
    assert runs.json()[0]["failure_code"] == "handler_failed"
    assert info["db"].execute(
        "SELECT status FROM ago_governed_tasks WHERE id=%s", (task["id"],),
    ).fetchone()["status"] == "failed"


def test_stale_tool_run_reconciliation_requires_operator_and_never_replays(case):
    from datetime import timedelta, datetime, timezone

    from ago.security import Principal
    from ago.task_store import TaskStore

    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    enroll(client, founder, reviewer, "tool:scorecard")
    _, employee = create_ai(client, founder)
    task = post(client, "/v1/tasks", founder, {
        "action": "tool:scorecard", "assignee_id": employee,
    })
    approval = post(client, "/v1/governance/approvals", founder, {
        "action": "tool:scorecard",
    })
    post(client, f"/v1/tasks/{task['id']}/approval", founder, {
        "approval_id": approval["request_id"],
    })
    decision(client, reviewer, approval["request_id"])
    TaskStore(info["db"]).authorize_and_start(
        task_id=task["id"],
        principal=Principal(info["founder_id"], info["tenant"], ("founder",)),
    )
    run_id = str(uuid4())
    info["db"].execute(
        """INSERT INTO ago_tool_runs
           (id,tenant_id,task_id,tool_code,executor_id,started_at)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (run_id, info["tenant"], task["id"], "tool:scorecard",
         info["founder_id"],
         datetime.now(timezone.utc) - timedelta(hours=2)),
    )
    assert client.post("/v1/tools/runs/recover-stale",
                       headers=reviewer).status_code == 403
    recovered = post(client, "/v1/tools/runs/recover-stale", founder)
    assert recovered["uncertain_runs"] == 1
    assert recovered["manual_reconciliation_required"] is True
    assert post(client, "/v1/tools/runs/recover-stale", founder)[
        "uncertain_runs"
    ] == 0
    assert info["db"].execute(
        "SELECT status FROM ago_tool_runs WHERE id=%s", (run_id,),
    ).fetchone()["status"] == "uncertain"
    assert info["db"].execute(
        "SELECT status FROM ago_governed_tasks WHERE id=%s", (task["id"],),
    ).fetchone()["status"] == "failed"
    post(client, f"/v1/tools/tasks/{task['id']}/run", founder, expected=403)


def test_qa_trigger_polls_sources_without_recursing_on_automation_outputs(case):
    client, headers, info = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    enroll(client, founder, reviewer, "tool:scorecard")
    dept, worker = create_ai(client, founder)
    source_task = post(client, "/v1/tasks", founder, {
        "action": "internal:brief", "assignee_id": worker,
    })
    approval = post(client, "/v1/governance/approvals", founder, {
        "action": "internal:brief",
    })
    post(client, f"/v1/tasks/{source_task['id']}/approval", founder, {
        "approval_id": approval["request_id"],
    })
    decision(client, reviewer, approval["request_id"])
    post(client, f"/v1/agents/tasks/{source_task['id']}/run", founder)
    post(client, f"/v1/tasks/{source_task['id']}/review", reviewer, {
        "verdict": "pass", "evidence": "Original AI outcome passed independent QA",
    })
    rule = post(client, "/v1/tools/automation/rules", founder, {
        "department_id": dept, "assignee_id": worker,
        "code": "tool:scorecard", "trigger": "qa_pass",
    })
    scan = post(client, "/v1/tools/automation/scan", founder, {"limit": 5})
    assert len(scan["firings"]) == 1
    firing = scan["firings"][0]
    assert firing["execution_permitted"] is False
    assert post(client, "/v1/tools/automation/scan", founder, {
        "limit": 5,
    })["firings"] == []
    decision(client, reviewer, firing["approval_id"])
    post(client, f"/v1/tools/tasks/{firing['task_id']}/run", founder)
    post(client, f"/v1/tasks/{firing['task_id']}/review", reviewer, {
        "verdict": "pass", "evidence": "Automation report reviewed",
    })
    assert post(client, "/v1/tools/automation/scan", founder, {
        "limit": 5,
    })["firings"] == []
    post(client, f"/v1/tools/automation/rules/{rule['id']}/fire", founder, {
        "source_id": firing["task_id"],
    }, expected=403)
    post(client, f"/v1/tools/automation/rules/{rule['id']}/disable", founder)
    post(client, f"/v1/tools/automation/rules/{rule['id']}/fire", founder, {
        "source_id": source_task["id"],
    }, expected=403)


def test_postgresql_blocks_forged_enrollment_and_finished_run_tampering(case):
    client, headers, info = case
    psycopg = pytest.importorskip("psycopg")
    founder, reviewer = headers["founder"], headers["reviewer"]
    pending = post(client, "/v1/tools/enrollments", founder, {
        "code": "tool:scorecard", "rationale": "Approval not yet given",
    })
    with pytest.raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                """UPDATE ago_tool_enrollments SET status='active',
                   changed_at=now() WHERE id=%s""",
                (pending["id"],),
            )
    decision(client, reviewer, pending["approval_id"])
    post(client, f"/v1/tools/enrollments/{pending['id']}/reconcile", founder)
    _, worker = create_ai(client, founder)
    task = post(client, "/v1/tasks", founder, {
        "action": "tool:scorecard", "assignee_id": worker,
    })
    request = post(client, "/v1/governance/approvals", founder, {
        "action": "tool:scorecard",
    })
    post(client, f"/v1/tasks/{task['id']}/approval", founder, {
        "approval_id": request["request_id"],
    })
    decision(client, reviewer, request["request_id"])
    run = post(client, f"/v1/tools/tasks/{task['id']}/run", founder)
    with pytest.raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                "UPDATE ago_tool_runs SET output='{}'::jsonb WHERE id=%s",
                (run["id"],),
            )
    with pytest.raises(psycopg.errors.RaiseException):
        with info["db"].transaction():
            info["db"].execute(
                "DELETE FROM ago_tool_run_evidence WHERE run_id=%s",
                (run["id"],),
            )
