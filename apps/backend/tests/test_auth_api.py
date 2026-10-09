from fastapi import FastAPI
from fastapi.testclient import TestClient

from ago.auth_api import AuthDependencies, build_auth_router
from ago.security import Principal, SessionTokens


class Identity:
    def authenticate(self, tenant_id, email, password):
        if (tenant_id, email, password) == ("tenant-a", "user@example.com", "password"):
            return Principal("user-1", "tenant-a", ("reader",))
        return None


def test_opt_in_auth_router_issues_valid_token():
    tokens = SessionTokens("a" * 48)
    app = FastAPI()
    app.include_router(build_auth_router(AuthDependencies(
        identity=Identity(), tokens=tokens, tenant_validator=lambda tenant: tenant == "tenant-a"
    )))
    client = TestClient(app)
    response = client.post("/auth/login", json={
        "tenant_id": "tenant-a", "email": "user@example.com", "password": "password"
    })
    assert response.status_code == 200
    body = response.json()
    assert tokens.verify(body["access_token"]).tenant_id == "tenant-a"
    assert body["token_type"] == "bearer"
    assert client.post("/auth/login", json={
        "tenant_id": "tenant-b", "email": "user@example.com", "password": "password"
    }).status_code == 401
    assert client.post("/auth/login", json={
        "tenant_id": "tenant-a", "email": "user@example.com", "password": "wrong"
    }).status_code == 401
