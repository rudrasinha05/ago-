"""M6 end-to-end HTTP regression on disposable PostgreSQL with real sessions."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import os
import pytest
from fastapi.testclient import TestClient

from ago import api_m2
from ago.bootstrap import bootstrap
from ago.main import create_app
from ago.organization_store import OrganizationStore
from ago.provision import add_reviewer


@pytest.fixture
def case(monkeypatch):
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Requires AGO_TEST_POSTGRES_DSN")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    monkeypatch.setenv("AGO_SESSION_SECRET", "m6-integration-test-signing-key-123456789")
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, founder_id = bootstrap(
                db, organization="M6 Test Company",
                email="m6founder@example.test", password="founder-test-password-123",
            )
            org = OrganizationStore(db)
            departments = org.list_departments(tenant_id=tenant)
            executive = departments[0].id
            research = org.add_department(tenant_id=tenant, name="Research")
            assurance = org.add_department(tenant_id=tenant, name="Assurance")
            reviewer1 = add_reviewer(
                db, tenant_id=tenant, department_id=research.id,
                email="m6reviewer1@example.test", password="reviewer-test-password-123",
            )
            reviewer2 = add_reviewer(
                db, tenant_id=tenant, department_id=assurance.id,
                email="m6reviewer2@example.test", password="reviewer-test-password-123",
            )
            app = create_app()
            app.dependency_overrides[api_m2.db_connection] = lambda: db
            with TestClient(app) as client:
                def login(email, password):
                    result = client.post(
                        "/v1/sessions", json={
                            "tenant_id": tenant, "email": email, "password": password,
                        },
                    )
                    assert result.status_code == 200, result.text
                    return {"Authorization": "Bearer " + result.json()["access_token"]}
                headers = {
                    "founder": login("m6founder@example.test", "founder-test-password-123"),
                    "reviewer1": login("m6reviewer1@example.test", "reviewer-test-password-123"),
                    "reviewer2": login("m6reviewer2@example.test", "reviewer-test-password-123"),
                }
                yield client, headers, {
                    "tenant": tenant, "founder": founder_id,
                    "reviewer1": reviewer1, "reviewer2": reviewer2,
                    "executive": executive, "research": research.id,
                    "assurance": assurance.id,
                    "db": db,
                }
        finally:
            db.rollback()


def post(client, path, headers, body=None, expected=200):
    response = client.post(path, json=body or {}, headers=headers)
    assert response.status_code == expected, (path, response.status_code, response.text)
    return response.json()
