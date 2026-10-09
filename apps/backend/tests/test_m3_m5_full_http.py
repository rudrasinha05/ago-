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
