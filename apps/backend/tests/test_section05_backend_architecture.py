"""Request-scope substitution, strict authority inputs and safe error regressions."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ago import api_m2
from ago.backend_contracts import RepositoryScope
from ago.main import create_app
from ago.organization import Department
from ago.organization_store import OrganizationStore
from ago.plan_execution import PlanExecution
from ago.repository_ports import (
    REPOSITORY_BINDINGS,
    OrganizationStorePort,
    SecurityControlsPort,
    TaskStorePort,
)
from ago.security import Principal
from ago.task_store import TaskStore

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "backend_architecture", ROOT / "scripts/check_backend_architecture.py"
)
architecture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(architecture)


class NoSQL:
    def execute(self, *_args, **_kwargs):
        raise AssertionError("Unexpected SQL escaped injected ports")


class Permitted:
    def __init__(self, _connection):
        pass

    def permitted(self, principal, _permission, tenant_id):
        return principal.tenant_id == tenant_id


@pytest.fixture
def request_app(monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    app = create_app()
    actor = Principal(str(uuid4()), str(uuid4()), ("operator",))
    app.dependency_overrides[api_m2.db_connection] = lambda: NoSQL()
    app.dependency_overrides[api_m2.authenticated] = lambda: actor
    app.state.repository_overrides = {SecurityControlsPort: Permitted}
    return app, actor


def test_all_backend_components_and_layer_contracts_match():
    assert architecture.check() == []


def test_request_scope_isolated_and_protocol_and_implementation_share_one_instance():
    first = RepositoryScope(NoSQL(), bindings=REPOSITORY_BINDINGS)
    second = RepositoryScope(NoSQL(), bindings=REPOSITORY_BINDINGS)
    assert first.resolve(OrganizationStorePort) is first.resolve(OrganizationStore)
    assert first.resolve(OrganizationStorePort) is not second.resolve(OrganizationStorePort)
    assert first.resolve(OrganizationStore).connection is first.connection


def test_overrides_cascade_from_protocol_into_application_dependencies():
    marker = object()
    scope = RepositoryScope(
        NoSQL(), bindings=REPOSITORY_BINDINGS, overrides={TaskStorePort: lambda _db: marker}
    )
    service = scope.resolve(PlanExecution)
    assert service.repositories is scope
    assert service.repositories.resolve(TaskStore) is marker
    assert scope.resolve(TaskStorePort) is marker


def test_constructor_options_do_not_reuse_a_different_handler_configuration():
    class Component:
        def __init__(self, _db, *, handlers=None):
            self.handlers = handlers

    scope = RepositoryScope(NoSQL())
    assert scope.resolve(Component, handlers={"one": 1}).handlers == {"one": 1}
    assert scope.resolve(Component, handlers={"two": 2}).handlers == {"two": 2}


def test_http_uses_substituted_port_current_actor_and_new_scope_each_request(request_app):
    app, actor = request_app
    instances = []

    class Organization:
        def __init__(self, connection, *, repositories):
            instances.append((self, connection, repositories))

        def add_department(self, *, tenant_id, name):
            assert tenant_id == actor.tenant_id
            return Department(str(uuid4()), tenant_id, name)

    app.state.repository_overrides[OrganizationStorePort] = Organization
    with TestClient(app) as client:
        for _ in range(2):
            result = client.post("/v1/organization/departments", json={"name": "Ops"})
            assert result.status_code == 200 and result.json()["tenant_id"] == actor.tenant_id
    assert len(instances) == 2
    assert instances[0][0] is not instances[1][0]
    assert instances[0][2] is not instances[1][2]


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Ops", "authorized": True},
        {"name": "Ops", "tenant_id": str(uuid4())},
        {"name": "Ops", "actor_id": str(uuid4())},
    ],
)
def test_unknown_authority_fields_rejected_before_mutation(request_app, payload):
    app, _actor = request_app
    app.state.repository_overrides[OrganizationStorePort] = lambda _db: pytest.fail(
        "Mutation port reached"
    )
    with TestClient(app) as client:
        response = client.post("/v1/organization/departments", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_denied_permission_still_blocks_an_injected_mutation(request_app):
    app, _actor = request_app

    class Denied(Permitted):
        def permitted(self, *_args):
            return False

    app.state.repository_overrides[SecurityControlsPort] = Denied
    app.state.repository_overrides[OrganizationStorePort] = lambda _db: pytest.fail(
        "Denied mutation reached"
    )
    with TestClient(app) as client:
        response = client.post("/v1/organization/departments", json={"name": "Ops"})
    assert response.status_code == 403


def test_strict_boolean_and_employee_kind_and_visibility():
    for model, payload in [
        (api_m2.DecisionInput, {"approve": "false", "reason": "review"}),
        (api_m2.EmployeeInput, {"department_id": str(uuid4()), "name": "Agent", "kind": "root"}),
        (api_m2.MemoryInput, {"content": "private", "visibility": "public"}),
    ]:
        with pytest.raises(ValueError):
            model.model_validate(payload)
    password = "  exact password  "
    assert (
        api_m2.Login(tenant_id=str(uuid4()), email="a@example.test", password=password).password
        == password
    )


@pytest.mark.parametrize(
    "kind,status,code",
    [
        (ValueError, 400, "invalid_request"),
        (PermissionError, 403, "permission_denied"),
        (LookupError, 404, "not_found"),
        (RuntimeError, 500, "internal_error"),
    ],
)
def test_business_errors_have_safe_uniform_correlated_envelopes(monkeypatch, kind, status, code):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    app = create_app()

    @app.get("/test-business-error")
    def fail():
        raise kind("dsn-password-private-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-business-error", headers={"x-request-id": "section5-test"})
    assert response.status_code == status
    assert response.json()["error"] == {"code": code, "request_id": "section5-test"}
    assert response.headers["x-request-id"] == "section5-test"
    assert "dsn-password-private-secret" not in response.text


def test_unauthenticated_bearer_challenge_kept_and_no_database_opened(monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    app = create_app()
    app.dependency_overrides[api_m2.db_connection] = lambda: pytest.fail(
        "Unauthenticated DB access"
    )
    with TestClient(app) as client:
        response = client.get("/v1/console/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "authentication_required"


def test_validation_does_not_echo_secret_input_or_invalid_json(request_app):
    app, _actor = request_app
    with TestClient(app) as client:
        response = client.post(
            "/v1/sessions",
            json={
                "tenant_id": "password-secret",
                "email": "x",
                "password": {"private": "credential"},
            },
        )
        malformed = client.post(
            "/v1/sessions",
            content="{secret-invalid-json",
            headers={"content-type": "application/json"},
        )
    for result in (response, malformed):
        assert result.status_code == 422
        assert "credential" not in result.text and "password-secret" not in result.text
        assert "secret-invalid-json" not in result.text
        assert all(set(e) == {"loc", "type", "msg"} for e in result.json()["detail"])


def test_postgres_conflict_redacts_database_error(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    app = create_app()

    @app.get("/test-conflict")
    def conflict():
        raise psycopg.IntegrityError("private constraint data")

    with TestClient(app) as client:
        response = client.get("/test-conflict")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert "private constraint data" not in response.text


@pytest.fixture
def copy_repo(tmp_path):
    shutil.copytree(
        ROOT,
        tmp_path / "repo",
        ignore=shutil.ignore_patterns(
            ".git", "node_modules", ".next", "out", "__pycache__", ".pytest_cache", "*.egg-info"
        ),
    )
    return tmp_path / "repo"


def test_transport_sql_negative(copy_repo):
    p = copy_repo / "apps/backend/ago/api_brain.py"
    p.write_text(p.read_text() + '\ndef forbidden(db):\n    return db.execute("SELECT 1")\n')
    assert "raw-database-in-layer:api_brain" in architecture.check(copy_repo)


def test_concrete_repository_construction_negative(copy_repo):
    p = copy_repo / "apps/backend/ago/api_brain.py"
    p.write_text(p.read_text() + "\ndef forbidden(db):\n    return GoalStore(db)\n")
    assert "concrete-construction:api_brain:GoalStore" in architecture.check(copy_repo)


def test_unreviewed_repository_interface_negative(copy_repo):
    p = copy_repo / "apps/backend/ago/goals.py"
    p.write_text(p.read_text() + "\n    def bypass(self, tenant):\n        return tenant\n")
    assert "repository-contract-drift" in architecture.check(copy_repo)


def test_permissive_request_model_negative(copy_repo):
    p = copy_repo / "apps/backend/ago/api_brain.py"
    p.write_text(p.read_text() + "\nclass UnsafeInput(BaseModel):\n    authorized: bool\n")
    assert "permissive-input:api_brain:UnsafeInput" in architecture.check(copy_repo)


def test_port_signature_negative(copy_repo):
    p = copy_repo / "apps/backend/ago/repository_ports.py"
    p.write_text(p.read_text().replace("permission: str", "permission: int", 1))
    assert any(e.startswith("port-signature-drift:") for e in architecture.check(copy_repo))


def test_application_sql_negative(copy_repo):
    p = copy_repo / 'apps/backend/ago/plan_execution.py'
    p.write_text(p.read_text()+'\ndef forbidden(db):\n    return db.execute("SELECT 1")\n')
    assert 'raw-database-in-layer:plan_execution' in architecture.check(copy_repo)


def test_dynamic_sql_selectors_are_closed_before_database_execution():
    from ago.meta_brain_queries import MetaBrainQueries
    from ago.scorecard_queries import ScorecardQueries
    with pytest.raises(ValueError):
        ScorecardQueries(NoSQL()).select_tenant_count_01(('tenant',), table='ago_users; DELETE FROM ago_users')
    with pytest.raises(ValueError):
        MetaBrainQueries(NoSQL()).select_ago_meta_recommendations_07(('tenant',), extra=' OR true')


def test_every_structural_port_annotation_resolves():
    import inspect
    from typing import get_type_hints
    for port in REPOSITORY_BINDINGS:
        for name, method in inspect.getmembers(port, inspect.isfunction):
            if not name.startswith('_'):
                assert 'return' in get_type_hints(method)
