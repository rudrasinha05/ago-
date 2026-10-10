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
