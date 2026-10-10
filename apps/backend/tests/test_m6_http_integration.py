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


def test_handoff_reviewer_boundary(case):
    client, headers, ids = case
    request = post(client, "/v1/operations/handoffs", headers["founder"], {
        "sender_department_id": ids["executive"],
        "receiver_department_id": ids["research"],
        "assignee_id": ids["reviewer1"],
        "title": "Research review",
        "brief": "Review the research material",
        "operation_key": "handoff-test",
    })
    url = f"/v1/operations/handoffs/{request['id']}/transition"
    data = {"decision": "accepted", "note": "Acknowledged"}
    post(client, url, headers["founder"], data, expected=403)
    post(client, url, headers["reviewer2"], data, expected=403)
    post(client, url, headers["reviewer1"], data)
    post(client, url, headers["reviewer1"], data, expected=403)
    assert post(client, url, headers["reviewer1"], {
        "decision": "completed", "note": "Completed peer review",
    })["status"] == "completed"
    history = client.get(
        f"/v1/operations/handoffs/{request['id']}/history",
        headers=headers["reviewer1"],
    )
    assert history.status_code == 200, history.text
    assert [event["event"] for event in history.json()] == [
        "requested", "accepted", "completed",
    ]


def test_private_calendar_and_append_only_responses(case):
    client, headers, ids = case
    begins = datetime.now(timezone.utc) + timedelta(days=2)
    ends = begins + timedelta(minutes=45)
    event = post(client, "/v1/operations/calendar", headers["founder"], {
        "title": "Private planning",
        "starts_at": begins.isoformat(), "ends_at": ends.isoformat(),
        "visibility": "private", "operation_key": "private-m6-event",
        "employee_ids": [ids["reviewer1"]],
    })
    route = "/v1/operations/calendar"
    params = {"start": (begins-timedelta(minutes=1)).isoformat(),
              "end": (ends+timedelta(minutes=1)).isoformat()}
    assert len(client.get(route, headers=headers["founder"], params=params).json()) == 1
    assert len(client.get(route, headers=headers["reviewer1"], params=params).json()) == 1
    assert client.get(route, headers=headers["reviewer2"], params=params).json() == []
    post(client, f"/v1/operations/calendar/{event['id']}/rsvp",
         headers["reviewer1"], {"response": "accepted"})
    post(client, f"/v1/operations/calendar/{event['id']}/cancel",
         headers["reviewer1"], expected=403)
    post(client, f"/v1/operations/calendar/{event['id']}/cancel",
         headers["founder"])
    post(client, f"/v1/operations/calendar/{event['id']}/rsvp",
         headers["reviewer1"], {"response": "declined"}, expected=403)
    history = client.get(
        f"/v1/operations/calendar/{event['id']}/history",
        headers=headers["founder"],
    )
    assert history.status_code == 200, history.text
    assert [item["event"] for item in history.json()] == [
        "scheduled", "accepted", "cancelled",
    ]


def test_independent_knowledge_review_and_graph(case):
    client, headers, ids = case
    new_node = "/v1/knowledge/nodes"
    first = post(client, new_node, headers["founder"], {
        "kind": "fact", "label": "Internal baseline",
        "statement": "Historical baseline recorded for peer review",
        "source_ref": "internal:artifact:baseline",
    })
    second = post(client, new_node, headers["founder"], {
        "kind": "artifact", "label": "Review evidence",
        "statement": "Supporting internal evidence was attached",
        "source_ref": "internal:artifact:source-2",
    })
    assert client.get(new_node, headers=headers["founder"]).json() == []
    first_review = f"/v1/knowledge/nodes/{first['id']}/review"
    post(client, first_review, headers["founder"],
         {"approve": True, "note": "Self-review"}, expected=403)
    post(client, first_review, headers["reviewer1"],
         {"approve": True, "note": "Source inspected"})
    post(client, f"/v1/knowledge/nodes/{second['id']}/review", headers["reviewer2"],
         {"approve": True, "note": "Artifact inspected"})
    verified = client.get(new_node, headers=headers["reviewer1"])
    assert verified.status_code == 200
    assert len(verified.json()) == 2
    edge = post(client, "/v1/knowledge/edges", headers["founder"], {
        "from_id": first["id"], "to_id": second["id"], "relation": "supports",
    })
    assert edge["id"]
    edges = client.get(
        f"/v1/knowledge/nodes/{first['id']}/edges", headers=headers["founder"],
    )
    assert edges.status_code == 200 and len(edges.json()) == 1
    post(client, first_review, headers["reviewer2"],
         {"approve": False, "note": "Replay"}, expected=403)


def test_council_needs_two_humans_and_m2_approval(case):
    client, headers, ids = case
    motion = post(client, "/v1/council/motions", headers["founder"], {
        "title": "Approve internal review policy",
        "rationale": "Review process should have independent evidence",
        "required_votes": 2,
    })
    vote_url = f"/v1/council/motions/{motion['id']}/votes"
    finalize_url = f"/v1/council/motions/{motion['id']}/finalize"
    post(client, vote_url, headers["founder"],
         {"vote": "yes", "reason": "Self vote"}, expected=403)
    post(client, finalize_url, headers["founder"], expected=403)
    post(client, vote_url, headers["reviewer1"],
         {"vote": "yes", "reason": "Reviewed evidence"})
    post(client, vote_url, headers["reviewer2"],
         {"vote": "yes", "reason": "Second independent review"})
    post(client, finalize_url, headers["founder"], expected=403)
