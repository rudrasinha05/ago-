"""M9 same-origin browser entry, security headers, and authenticated session contract."""
from __future__ import annotations

import os
from importlib.resources import files
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ago import api_m2
from ago.main import create_app


def test_public_console_is_static_only_with_strict_headers():
    with TestClient(create_app()) as client:
        entry = client.get("/console/", follow_redirects=False)
        assert entry.status_code == 200
        assert entry.headers["content-type"].startswith("text/html")
        assert 'script-src \'self\'' in entry.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in entry.headers["content-security-policy"]
        assert "connect-src 'self'" in entry.headers["content-security-policy"]
        assert "unsafe-inline" not in entry.headers["content-security-policy"]
        assert entry.headers["x-frame-options"] == "DENY"
        assert entry.headers["x-content-type-options"] == "nosniff"
        assert entry.headers["referrer-policy"] == "no-referrer"
        assert "no-store" in entry.headers["cache-control"]
        assert "access-control-allow-origin" not in entry.headers
        assert "login-form" in entry.text
        assert 'src="/console/assets/app.js"' in entry.text
        assert 'href="/console/assets/styles.css"' in entry.text
        assert "No tokens are stored" in entry.text


def test_console_redirect_and_assets_are_first_party_and_no_store():
    with TestClient(create_app()) as client:
        redirect = client.get("/console", follow_redirects=False)
        assert redirect.status_code == 308
        assert redirect.headers["location"] == "/console/"
        assert "no-store" in redirect.headers["cache-control"]
        for asset in ("app.js", "actions.js", "views.js", "core.js", "styles.css"):
            response = client.get("/console/assets/" + asset)
            assert response.status_code == 200, (asset, response.text[:250])
            assert "no-store" in response.headers["cache-control"]
            assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
            assert len(response.content) > 200
        assert client.get("/console/assets/missing.js").status_code == 404


def test_auth_protected_endpoints_remain_closed_when_static_console_is_public():
    app = create_app()
    app.dependency_overrides[api_m2.db_connection] = lambda: object()
    with TestClient(app) as client:
        assert client.get("/console/").status_code == 200
        assert client.get("/v1/console/me").status_code == 401
        assert client.post("/v1/console/logout").status_code == 401
        assert client.get("/v1/insights/scorecard").status_code == 401
        assert client.get("/v1/meta/brief").status_code == 401


def test_console_assets_ship_in_python_package_and_do_not_persist_tokens():
    root = files("ago").joinpath("console")
    for name in ("index.html","app.js","actions.js","views.js",
                 "styles.css","core.js","package.json"):
        assert root.joinpath(name).is_file(), name
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    core = root.joinpath("core.js").read_text(encoding="utf-8")
    assert "localStorage" not in script + core
    assert "sessionStorage" not in script + core
    assert "document.cookie" not in script + core
    assert '"/v1/console/logout"' in script
    assert '"/v1/console/me"' in script
    assert "credentials: \"omit\"" in core
    assert "same-origin" in core


@pytest.fixture
def live_console(monkeypatch):
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Migrated disposable AGO_TEST_POSTGRES_DSN required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from ago.bootstrap import bootstrap
    from ago.provision import add_reviewer

    monkeypatch.setenv("AGO_SESSION_SECRET", "m9-integration-only-long-session-key-123456789")
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        try:
            tenant, founder = bootstrap(
                db, organization="M9 UI Acceptance",
                email="m9founder@example.test",
                password="founder-password-123",
            )
            reviewer = add_reviewer(
                db, tenant_id=tenant, email="m9reviewer@example.test",
                password="reviewer-password-123",
            )
            app = create_app()
            app.dependency_overrides[api_m2.db_connection] = lambda: db
            with TestClient(app) as client:
                yield client, db, tenant, founder, reviewer
        finally:
            db.rollback()


def test_console_session_identity_is_from_database_and_logout_revokes(live_console):
    client, db, tenant, founder, reviewer = live_console
    login = client.post("/v1/sessions", json={
        "tenant_id": tenant, "email": "m9founder@example.test",
        "password": "founder-password-123",
    })
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    me = client.get("/v1/console/me", headers=headers)
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["id"] == founder
    assert payload["tenant_id"] == tenant
    assert payload["email"] == "m9founder@example.test"
    assert "founder" in payload["roles"]
    assert "approval:request" in payload["permissions"]
    assert "meta:simulate" in payload["permissions"]
    assert "password" not in payload and "password_hash" not in payload
    assert "access_token" not in payload
    signed_out = client.post("/v1/console/logout", headers=headers)
    assert signed_out.status_code == 200
    assert signed_out.json() == {"status": "revoked"}
    assert client.get("/v1/console/me", headers=headers).status_code == 401
    assert client.post("/v1/console/logout", headers=headers).status_code == 401


def test_console_role_is_persistent_and_does_not_inherit_founder_permissions(live_console):
    client, db, tenant, founder, reviewer = live_console
    login = client.post("/v1/sessions", json={
        "tenant_id": tenant, "email": "m9reviewer@example.test",
        "password": "reviewer-password-123",
    })
    assert login.status_code == 200
    header = {"Authorization": "Bearer " + login.json()["access_token"]}
    me = client.get("/v1/console/me", headers=header)
    assert me.status_code == 200
    assert me.json()["id"] == reviewer
    assert "reviewer" in me.json()["roles"]
    assert "approval:decide" in me.json()["permissions"]
    assert "brain:manage" not in me.json()["permissions"]
    assert client.post("/v1/brain/goals", headers=header,
                       json={"title":"Unauthorized strategic goal"}).status_code == 403
    assert client.get("/v1/console/me").status_code == 401


def test_console_self_profile_cannot_be_switched_by_query_parameter(live_console):
    client, db, tenant, founder, reviewer = live_console
    other, other_user = None, None
    from ago.bootstrap import bootstrap
    other, other_user = bootstrap(
        db, organization="M9 Isolated Counterparty " + str(uuid4()),
        email="otherm9@example.test", password="other-password-123",
    )
    login = client.post("/v1/sessions", json={
        "tenant_id": tenant, "email":"m9founder@example.test",
        "password":"founder-password-123",
    })
    auth = {"Authorization": "Bearer " + login.json()["access_token"]}
    result = client.get("/v1/console/me?tenant_id=" + other +
                        "&user_id=" + other_user, headers=auth)
    assert result.status_code == 200
    assert result.json()["tenant_id"] == tenant
    assert result.json()["id"] == founder
