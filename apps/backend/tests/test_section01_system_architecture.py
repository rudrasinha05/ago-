"""System traceability and all-router fail-closed perimeter regression tests."""
import importlib.util
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ago.api_m2 import db_connection
from ago.main import create_app

ROOT = Path(__file__).resolve().parents[3]
# These proof-exchange routes deliberately cannot require an existing bearer.
# The list is exact; every other /v1 operation remains in the anonymous denial gate.
PUBLIC_AUTH_ROUTES = {
    '/v1/sessions', '/v1/security/mfa/confirm', '/v1/security/tickets/redeem',
    '/v1/security/sso/start', '/v1/security/sso/callback', '/v1/security/sso/session',
}
spec = importlib.util.spec_from_file_location(
    "system_architecture", ROOT / "scripts/check_system_architecture.py",
)
architecture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(architecture)


def test_system_architecture_matches_source():
    assert architecture.check() == []


@pytest.fixture
def copied_system(tmp_path):
    shutil.copytree(ROOT / "apps/backend/ago", tmp_path / "apps/backend/ago")
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    return tmp_path


def test_missing_runtime_router_fails_traceability(copied_system):
    path = copied_system / "apps/backend/ago/main.py"
    path.write_text(path.read_text().replace("app.include_router(meta_router)", "pass"))
    assert "router-composition-drift" in architecture.check(copied_system)


def test_stale_module_inventory_fails_traceability(copied_system):
    path = copied_system / "docs/architecture/SECTION_01_MODULE_INVENTORY.md"
    path.write_text(path.read_text().replace("| governance |", "| strategy |", 1))
    assert "module-inventory-drift" in architecture.check(copied_system)


def test_missing_architecture_document_fails_traceability(copied_system):
    (copied_system / "docs/architecture/SECTION_01_OVERALL_SYSTEM_ARCHITECTURE.md").unlink()
    assert any(e.startswith("missing-document:") for e in architecture.check(copied_system))


@pytest.mark.parametrize("database_available", [False, True])
def test_every_private_api_operation_rejects_anonymous(monkeypatch, database_available):
    monkeypatch.delenv("AGO_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_SESSION_SECRET", "section01_test_secret_not_for_production_12345")
    app = create_app()
    if database_available:
        class NoQueries:
            def execute(self, *args, **kwargs):
                raise AssertionError("Anonymous request reached a database query")
        app.dependency_overrides[db_connection] = lambda: NoQueries()
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    checked = 0
    for path, operations in schema["paths"].items():
        if not path.startswith("/v1/") or path in PUBLIC_AUTH_ROUTES:
            continue
        # Authentication/database outage must prevent business execution.
        actual = path
        actual = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000001", actual)
        for method in operations:
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            response = client.request(method, actual, json={})
            expected = {401} if database_available else {401, 503}
            assert response.status_code in expected, (method, path, response.status_code)
            checked += 1
    assert checked >= 50
