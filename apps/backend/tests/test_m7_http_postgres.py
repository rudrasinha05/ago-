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
