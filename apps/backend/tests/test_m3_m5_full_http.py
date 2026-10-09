"""M3-M5 end-to-end HTTP acceptance using real signed sessions and PostgreSQL."""
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
        pytest.skip("PostgreSQL test database required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    monkeypatch.setenv("AGO_SESSION_SECRET", "m3-m5-integration-test-signing-key-123456")
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, _ = bootstrap(
                db, organization="M3-M5 Acceptance",
                email="founder@example.test", password="founder-password-123",
            )
            add_reviewer(db, tenant_id=tenant, email="reviewer@example.test",
                         password="reviewer-password-123")
            app = create_app()
            app.dependency_overrides[api_m2.db_connection] = lambda: db
            with TestClient(app) as client:
                def login(email, password):
                    response = client.post(
                        "/v1/sessions", json={"tenant_id": tenant,
                        "email": email, "password": password},
                    )
                    assert response.status_code == 200, response.text
                    return {"Authorization": "Bearer " + response.json()["access_token"]}
                founder = login("founder@example.test", "founder-password-123")
                reviewer = login("reviewer@example.test", "reviewer-password-123")
                yield client, founder, reviewer
        finally:
            db.rollback()


def post(client, path, headers, body=None):
    response = client.post(path, json=body or {}, headers=headers)
    assert response.status_code == 200, (path, response.status_code, response.text)
    return response.json()


def test_company_plan_agent_and_economics_workflow(case):
    client, founder, reviewer = case
    assert client.get("/v1/brain/goals").status_code == 401
    goal = post(client, "/v1/brain/goals", founder, {"title": "Improve research"})
    plan = post(client, "/v1/brain/plans", founder,
                {"goal_id": goal["id"], "title": "Research plan"})
    departments = client.get("/v1/organization/departments", headers=founder).json()
    employee = post(client, "/v1/organization/employees", founder,
                    {"department_id": departments[0]["id"],
                     "name": "AI researcher", "kind": "ai"})
    post(client, f"/v1/brain/plans/{plan['id']}/steps", founder,
         {"action": "internal:brief", "assignee_id": employee["id"]})
    strategy = post(client, f"/v1/brain/plans/{plan['id']}/submit", founder)
    url = f"/v1/brain/plans/{plan['id']}/activate"
    assert client.post(url, headers=founder).status_code == 403
    post(client, f"/v1/governance/approvals/{strategy['approval_id']}/decision",
         reviewer, {"approve": True, "reason": "Independent strategy review"})
    post(client, url, founder)
    task = post(client, f"/v1/brain/plans/{plan['id']}/materialize", founder)
    task_id = task["task_ids"][0]

    action_approval = post(client, "/v1/governance/approvals", founder,
                           {"action": "internal:brief"})
    post(client, f"/v1/tasks/{task_id}/approval", founder,
         {"approval_id": action_approval["request_id"]})
    assert client.post(f"/v1/agents/tasks/{task_id}/run", headers=founder).status_code == 403
    post(client, f"/v1/governance/approvals/{action_approval['request_id']}/decision",
         reviewer, {"approve": True, "reason": "Agent action reviewed"})
    result = post(client, f"/v1/agents/tasks/{task_id}/run", founder)
    assert result["status"] == "completed"
    assert result["result"]["requires_human_qa"]
    assert client.post(f"/v1/agents/tasks/{task_id}/run", headers=founder).status_code == 403
    post(client, f"/v1/tasks/{task_id}/review", reviewer,
         {"verdict": "pass", "evidence": "Human inspected generated brief"})
    post(client, "/v1/insights/budget", founder, {"ceiling": "25"})
    first = post(client, "/v1/insights/usage", founder,
                 {"operation_key": "research-one", "amount": "4", "category": "research"})
    assert first["charged"] is True
    assert not post(client, "/v1/insights/usage", founder,
                    {"operation_key": "research-one", "amount": "4",
                     "category": "research"})["charged"]

    preview = post(client, "/v1/insights/simulate", founder,
                   {"planned_actions": 20, "cost_per_action": "2",
                    "failure_percent": 40})
    assert preview["simulation_only"]
    assert "budget_shortfall" in preview["risk_flags"]
    experiment = post(client, "/v1/insights/experiments", founder,
                      {"hypothesis": "Try smaller groups",
                       "baseline": "Current process",
                       "candidate": "Small independent teams"})
    post(client, f"/v1/governance/approvals/{experiment['approval_id']}/decision",
         reviewer, {"approve": True, "reason": "Hypothesis approved for study"})
    score = client.get("/v1/insights/scorecard", headers=founder)
    assert score.status_code == 200, score.text
    assert score.json()["counts"]["agent_runs"] == 1
    assert score.json()["counts"]["experiments"] == 1
    assert score.json()["virtual_credit_budget"]["consumed"] == "4.0000"
    assert client.get("/v1/insights/experiments", headers=reviewer).status_code == 403
