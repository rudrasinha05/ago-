"""M10 adversarial production ingress and fail-closed configuration checks."""
from __future__ import annotations

import hashlib
import os

import pytest
from fastapi.testclient import TestClient

from ago.main import create_app
from ago.release_security import ReleasePolicy, schema_integrity


@pytest.fixture
def prod(monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    monkeypatch.setenv("AGO_SESSION_SECRET", "V8Ux4zL9!tK3-Qv2#Yw7rP0_mH5Gc6XJ6uDsN1oB9aAF82zQ")
    monkeypatch.setenv("AGO_ALLOWED_HOSTS", "ago.example.com")
    monkeypatch.setenv("AGO_POSTGRES_DSN",
        "postgresql://ago:placeholder@db.example.com:5432/company"
        "?sslmode=verify-full&sslrootcert=/etc/ssl/approved-root.pem")
    monkeypatch.setenv("AGO_ENABLE_PAID_MODELS", "false")
    monkeypatch.setenv("AGO_M8_EXTERNAL_ENABLED", "false")
    monkeypatch.delenv("AGO_DEBUG", raising=False)


def test_production_rejects_missing_hosts_weak_secrets_and_non_tls_database(prod, monkeypatch):
    assert ReleasePolicy.from_environment().production
    monkeypatch.delenv("AGO_ALLOWED_HOSTS")
    with pytest.raises(ValueError, match="HOSTS"):
        ReleasePolicy.from_environment()
    monkeypatch.setenv("AGO_ALLOWED_HOSTS", "ago.example.com")
    monkeypatch.setenv("AGO_SESSION_SECRET", "ci_only_signing_key_change_outside_ci_123456789")
    with pytest.raises(ValueError, match="SECRET"):
        ReleasePolicy.from_environment()
    monkeypatch.setenv("AGO_SESSION_SECRET", "V8Ux4zL9!tK3-Qv2#Yw7rP0_mH5Gc6XJ6uDsN1oB9aAF82zQ")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://user:pass@db.example.com/company")
    with pytest.raises(ValueError, match="TLS"):
        ReleasePolicy.from_environment()
    monkeypatch.setenv("AGO_POSTGRES_DSN",
        "postgresql://user:pass@db.example.com/company?sslmode=verify-full")
    with pytest.raises(ValueError, match="TLS"):
        ReleasePolicy.from_environment()


@pytest.mark.parametrize("hostname", [
    "*", "*.example.com", "localhost", "127.0.0.1",
    "db.internal", "staging.test", "https://ago.example.com",
    "ago.example.com:443", "ago.example.com,ago.example.com",
])
def test_production_disallows_wildcards_and_local_hosts(prod, monkeypatch, hostname):
    monkeypatch.setenv("AGO_ALLOWED_HOSTS", hostname)
    with pytest.raises(ValueError, match="HOSTS|public hosts"):
        ReleasePolicy.from_environment()


def test_production_disallows_optional_egress_and_debug(prod, monkeypatch):
    for name in ("AGO_ENABLE_PAID_MODELS", "AGO_M8_EXTERNAL_ENABLED", "AGO_DEBUG"):
        monkeypatch.setenv(name, "true")
        with pytest.raises(ValueError):
            ReleasePolicy.from_environment()
        monkeypatch.setenv(name, "false")


def test_production_rejects_oversize_body_limit_and_unknown_environment(prod, monkeypatch):
    monkeypatch.setenv("AGO_MAX_REQUEST_BYTES", "5000000")
    with pytest.raises(ValueError, match="body"):
        ReleasePolicy.from_environment()
    monkeypatch.setenv("AGO_MAX_REQUEST_BYTES", "1048576")
    monkeypatch.setenv("AGO_ENVIRONMENT", "prod_typo")
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        create_app()


def test_trusted_host_tls_docs_and_hsts_protection(prod):
    from ago import api_m2

    app = create_app()
    app.dependency_overrides[api_m2.db_connection] = lambda: object()
    with TestClient(app, base_url="https://ago.example.com") as client:
        console = client.get("/console/")
        assert console.status_code == 200
        assert console.headers["strict-transport-security"] == "max-age=31536000"
        assert "frame-ancestors 'none'" in console.headers["content-security-policy"]
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        private = client.get("/v1/console/me")
        assert private.status_code == 401
        assert private.headers["cache-control"] == "no-store, private"
        assert private.headers["x-content-type-options"] == "nosniff"
        assert "access-control-allow-origin" not in private.headers
        invalid_id = client.get("/console/", headers={"x-request-id": "\t"})
        assert invalid_id.headers["x-request-id"] != "\t"
    with TestClient(app, base_url="http://ago.example.com") as client:
        assert client.get("/console/").status_code == 426
        assert client.post("/v1/sessions", json={"bad": True}).status_code == 426
        # Health endpoints are intentionally safe for private container probes.
        assert client.get("/health/live").status_code == 200
    with TestClient(app, base_url="https://attacker.example") as client:
        assert client.get("/console/").status_code == 400


def test_content_length_and_chunked_oversize_are_denied_before_business_logic(
    monkeypatch,
):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_MAX_REQUEST_BYTES", "512")
    app = create_app()
    with TestClient(app) as client:
        result = client.post(
            "/v1/sessions", content=b"a"*513,
            headers={"content-type": "application/json"},
        )
        assert result.status_code == 413
        assert "Request body too large" in result.text

        def chunks():
            yield b"A"*300
            yield b"B"*300

        result = client.post(
            "/v1/sessions", content=chunks(),
            headers={"content-type": "application/json"},
        )
        assert result.status_code == 413
        assert "Bearer" not in result.text
        assert client.get("/console/").status_code == 200


def test_no_migrations_does_not_count_as_ready(monkeypatch, tmp_path):
    assert schema_integrity("postgresql://not-reached/ago", tmp_path) is False


def test_schema_integrity_checks_applied_real_ci_migrations():
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Migrated disposable PostgreSQL required")
    assert schema_integrity(dsn) is True


def test_schema_integrity_detects_changed_hash_without_updating_db(tmp_path, monkeypatch):
    from ago import release_security

    file = tmp_path / "001_demo.sql"
    file.write_text("SELECT 1;", encoding="utf-8")
    original = hashlib.sha256(file.read_bytes()).hexdigest()

    class FakeDB:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, _sql):
            class Rows:
                def fetchall(self): return [{"filename":"001_demo.sql","sha256":original}]
            return Rows()

    class FakePsycopg:
        @staticmethod
        def connect(*_a, **_kw): return FakeDB()

    import psycopg
    monkeypatch.setattr(psycopg, "connect", FakePsycopg.connect)
    assert release_security.schema_integrity("unused", tmp_path) is True
    file.write_text("SELECT 2;", encoding="utf-8")
    assert release_security.schema_integrity("unused", tmp_path) is False


def test_request_id_refuses_unprintable_and_long_values():
    app = create_app()
    with TestClient(app) as client:
        result = client.get("/console/", headers={"x-request-id":"x"*200})
        assert result.status_code == 200
        assert result.headers["x-request-id"] != "x"*200
        assert len(result.headers["x-request-id"]) == 36
