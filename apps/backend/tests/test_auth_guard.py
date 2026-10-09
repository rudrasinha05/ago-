from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from ago.auth_guard import permission_guard
from ago.security import AuthorizationError, Principal, SessionTokens


class Access:
    def require(self, principal, permission, *, resource_tenant_id):
        if principal.tenant_id != resource_tenant_id or permission != "tasks:read":
            raise AuthorizationError("denied")


def test_guard_requires_bearer_and_tenant_permission():
    tokens = SessionTokens("s" * 48)
    app = FastAPI()
    guard = permission_guard(
        tokens, Access(), "tasks:read",
        lambda request: request.path_params["tenant_id"],
    )

    @app.get("/tenants/{tenant_id}/tasks")
    def list_tasks(principal: Annotated[Principal, Depends(guard)]):
        return {"subject": principal.subject}

    client = TestClient(app)
    assert client.get("/tenants/tenant-a/tasks").status_code == 401
    token = tokens.issue(Principal("user", "tenant-a", ("reader",)))
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/tenants/tenant-a/tasks", headers=headers)
    assert response.status_code == 200
    assert response.json()["subject"] == "user"
    assert client.get("/tenants/tenant-b/tasks", headers=headers).status_code == 403
    assert client.get(
        "/tenants/tenant-a/tasks", headers={"Authorization": "Bearer invalid"}
    ).status_code == 401
