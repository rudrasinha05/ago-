"""Exercise M2 endpoints and tenant RBAC against migrated PostgreSQL, without network."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ago import api_m2
from ago.main import create_app
from ago.organization_store import OrganizationStore
from ago.security import Principal
from ago.security_controls import SecurityControls


@pytest.fixture
def case():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("AGO_TEST_POSTGRES_DSN required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant = str(uuid4())
            db.execute(
                "INSERT INTO ago_tenants(id, name) VALUES (%s, %s)",
                (tenant, "M2 HTTP integration"),
            )
            org = OrganizationStore(db)
            dept = org.add_department(tenant_id=tenant, name="Ops")
            agent = org.hire(
                tenant_id=tenant, department_id=dept.id,
                name="AI operator", kind="ai",
            )
            humans = [
                org.hire(
                    tenant_id=tenant, department_id=dept.id,
                    name=f"Human {n}", kind="human",
                )
                for n in range(2)
            ]
            controls = SecurityControls(db)
            for number, human in enumerate(humans):
                db.execute(
                    """INSERT INTO ago_users(id,tenant_id,email,password_hash)
                       VALUES (%s,%s,%s,%s)""",
                    (human.id, tenant, f"person{number}@example.test", "test-only"),
                )
                db.execute(
                    """INSERT INTO ago_user_roles(tenant_id,user_id,role)
                       VALUES (%s,%s,'operator')""",
                    (tenant, human.id),
                )
            for permission in (
                "approval:request", "approval:decide", "task:create",
                "task:execute", "qa:review",
            ):
                controls.grant(tenant, "operator", permission)
            current = {"actor": Principal(humans[0].id, tenant, ("operator",))}
            app = create_app()
            app.dependency_overrides[api_m2.db_connection] = lambda: db
            app.dependency_overrides[api_m2.authenticated] = lambda: current["actor"]
            with TestClient(app) as client:
                yield client, agent, humans, current
        finally:
            db.rollback()


def test_complete_http_approval_task_review_lifecycle(case):
    client, agent, humans, current = case
    proposal = client.post(
        "/v1/governance/approvals", json={"action": "internal:proof"},
    )
    assert proposal.status_code == 200, proposal.text
    approval_id = proposal.json()["request_id"]
    task = client.post(
        "/v1/tasks", json={"action": "internal:proof", "assignee_id": agent.id},
    )
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]
    linked = client.post(
        f"/v1/tasks/{task_id}/approval", json={"approval_id": approval_id},
    )
    assert linked.status_code == 200, linked.text
    assert client.post(f"/v1/tasks/{task_id}/start").status_code == 403
    decision_url = f"/v1/governance/approvals/{approval_id}/decision"
    assert client.post(
        decision_url, json={"approve": True, "reason": "self"},
    ).status_code == 403
    current["actor"] = Principal(
        humans[1].id, current["actor"].tenant_id, ("operator",),
    )
    decision = client.post(
        decision_url, json={"approve": True, "reason": "Independent review"},
    )
    assert decision.status_code == 200, decision.text
    started = client.post(f"/v1/tasks/{task_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"
    assert client.post(f"/v1/tasks/{task_id}/start").status_code == 403
    finished = client.post(
        f"/v1/tasks/{task_id}/finish", json={"success": True},
    )
    assert finished.status_code == 200, finished.text
    review = client.post(
        f"/v1/tasks/{task_id}/review",
        json={"verdict": "pass", "evidence": "Human reviewed output"},
    )
    assert review.status_code == 200, review.text
    duplicate = client.post(
        f"/v1/tasks/{task_id}/review",
        json={"verdict": "pass", "evidence": "Replay"},
    )
    assert duplicate.status_code == 409, duplicate.text


def test_rbac_revoke_immediately_blocks_new_task(case):
    client, agent, humans, current = case
    db = None
    for override, value in client.app.dependency_overrides.items():
        if override is api_m2.db_connection:
            db = value()
    assert db is not None
    controls = SecurityControls(db)
    controls.revoke_grant(current["actor"].tenant_id, "operator", "task:create")
    response = client.post(
        "/v1/tasks", json={"action": "internal:proof", "assignee_id": agent.id},
    )
    assert response.status_code == 403
