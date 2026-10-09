"""M2 HTTP API secure-by-default contract tests."""
from fastapi.testclient import TestClient

from ago.main import create_app


def test_all_m2_mutations_require_authenticated_session():
    client = TestClient(create_app())
    routes = [
        ("/v1/organization/departments", {"name": "Ops"}),
        ("/v1/organization/employees", {"department_id": "00000000-0000-0000-0000-000000000001", "name": "Agent", "kind": "ai"}),
        ("/v1/governance/approvals", {"action": "deploy:prod"}),
        ("/v1/tasks", {"action": "deploy:prod", "assignee_id": "00000000-0000-0000-0000-000000000001"}),
        ("/v1/memory", {"content": "private"}),
    ]
    for path, body in routes:
        assert client.post(path, json=body).status_code in (401, 503)


def test_m2_openapi_has_governance_routes():
    schema = TestClient(create_app()).get("/openapi.json").json()
    assert "/v1/tasks/{task_id}/start" in schema["paths"]
    assert "/v1/governance/approvals/{request_id}/decision" in schema["paths"]
    assert "/v1/tasks/{task_id}/review" in schema["paths"]


def test_no_client_authorization_flag_in_approval_body():
    schema = TestClient(create_app()).get("/openapi.json").json()
    request = schema["components"]["schemas"]["DecisionInput"]
    assert "authorized" not in request["properties"]
    assert "reviewer_id" not in request["properties"]
