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


def test_console_completes_separately_approved_task_and_human_qa(live_console):
    client, db, tenant, founder, reviewer = live_console
    def login(email, password):
        response = client.post("/v1/sessions", json={
            "tenant_id": tenant, "email": email, "password": password,
        })
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    owner = login("m9founder@example.test", "founder-password-123")
    human = login("m9reviewer@example.test", "reviewer-password-123")
    department = client.get("/v1/organization/departments", headers=owner).json()[0]["id"]
    ai = client.post("/v1/organization/employees", headers=owner, json={
        "department_id":department,"name":"M9 governed operator","kind":"ai",
    })
    assert ai.status_code == 200, ai.text
    task = client.post("/v1/tasks", headers=owner, json={
        "action":"internal:brief","assignee_id":ai.json()["id"],
    })
    assert task.status_code == 200, task.text
    task_id = task.json()["id"]
    request_url = f"/v1/console/tasks/{task_id}/request-approval"
    assert client.post(request_url, headers=human).status_code == 403
    proposed = client.post(request_url, headers=owner)
    assert proposed.status_code == 200, proposed.text
    approval = proposed.json()["approval_id"]
    assert proposed.json()["status"] == "waiting_approval"
    assert client.post(request_url, headers=owner).status_code == 403
    count = db.execute(
        "SELECT count(*) AS total FROM ago_approval_requests WHERE tenant_id=%s AND action=%s",
        (tenant, "internal:brief"),
    ).fetchone()["total"]
    assert count == 1
    assert client.post(f"/v1/agents/tasks/{task_id}/run",headers=owner).status_code == 403
    decision_url = f"/v1/governance/approvals/{approval}/decision"
    assert client.post(decision_url, headers=owner, json={
        "approve":True,"reason":"Forbidden self approval",
    }).status_code == 403
    approved = client.post(decision_url,headers=human,json={
        "approve":True,"reason":"Independent review of task scope",
    })
    assert approved.status_code == 200, approved.text
    executed = client.post(f"/v1/agents/tasks/{task_id}/run",headers=owner)
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "completed"
    empty = client.get("/v1/console/task-reviews",headers=human)
    assert empty.status_code == 200
    assert empty.json() == []
    reviewed = client.post(f"/v1/tasks/{task_id}/review",headers=human,json={
        "verdict":"pass","evidence":"Independent human inspected generated brief",
    })
    assert reviewed.status_code == 200, reviewed.text
    recorded = client.get("/v1/console/task-reviews",headers=human)
    assert recorded.status_code == 200
    assert recorded.json()[0]["task_id"] == task_id
    assert recorded.json()[0]["verdict"] == "pass"
    assert client.get("/v1/console/task-reviews").status_code == 401


def test_console_approval_request_rejects_foreign_tenant_without_orphans(live_console):
    client, db, tenant, founder, reviewer = live_console
    from ago.bootstrap import bootstrap as new_tenant
    foreign, foreign_user = new_tenant(
        db, organization="M9 Other " + str(uuid4()),
        email="m9other@example.test",password="other-password-123",
    )
    session = client.post("/v1/sessions",json={
        "tenant_id":foreign,"email":"m9other@example.test",
        "password":"other-password-123",
    })
    assert session.status_code == 200
    headers = {"Authorization":"Bearer "+session.json()["access_token"]}
    missing = str(uuid4())
    response = client.post(
        f"/v1/console/tasks/{missing}/request-approval",headers=headers,
    )
    assert response.status_code == 404
    approval_count = db.execute(
        "SELECT count(*) AS total FROM ago_approval_requests WHERE tenant_id=%s",
        (foreign,),
    ).fetchone()["total"]
    assert approval_count == 0
    assert client.get("/v1/console/task-reviews",headers=headers).json() == []


def test_calendar_invitee_flag_matches_actual_server_visibility(live_console):
    from datetime import datetime, timedelta, timezone

    client, db, tenant, founder, reviewer = live_console
    def login(email,password):
        result = client.post("/v1/sessions",json={
            "tenant_id":tenant,"email":email,"password":password,
        })
        return {"Authorization":"Bearer "+result.json()["access_token"]}

    owner = login("m9founder@example.test","founder-password-123")
    invitee = login("m9reviewer@example.test","reviewer-password-123")
    begins = datetime.now(timezone.utc) + timedelta(days=2)
    ends = begins + timedelta(hours=1)
    event = client.post("/v1/operations/calendar",headers=owner,json={
        "title":"Private team review","detail":"Human review meeting",
        "starts_at":begins.isoformat(),"ends_at":ends.isoformat(),
        "visibility":"private","operation_key":str(uuid4()),
        "employee_ids":[reviewer],
    })
    assert event.status_code == 200, event.text
    params={"start":(begins-timedelta(minutes=1)).isoformat(),
            "end":(ends+timedelta(minutes=1)).isoformat()}
    owner_rows=client.get("/v1/operations/calendar",headers=owner,params=params)
    invited_rows=client.get("/v1/operations/calendar",headers=invitee,params=params)
    assert owner_rows.status_code==200 and invited_rows.status_code==200
    assert owner_rows.json()[0]["invited"] is False
    assert invited_rows.json()[0]["invited"] is True
    response=client.post(
        f"/v1/operations/calendar/{event.json()['id']}/rsvp",
        headers=invitee,json={"response":"accepted"},
    )
    assert response.status_code==200,response.text
