"""M12 local founder start: redacted, no migration, atomic and nonproduction."""
from __future__ import annotations

import contextlib
import json
import os
from uuid import uuid4

import pytest

from ago import local_ops


LOCAL_DSN = "postgresql://operator:UNSAFE_PRIVATE_VALUE@localhost:5432/ago_local"


@pytest.fixture
def local_environment(monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", LOCAL_DSN)
    monkeypatch.delenv("AGO_SESSION_SECRET", raising=False)


def test_readonly_doctor_is_redacted_and_does_not_apply_migrations(
    local_environment, capsys,
):
    seen = []
    result = local_ops.doctor(verify_schema=lambda dsn: seen.append(dsn) or True)
    assert result.ready
    assert result.database_local
    assert result.signing_secret == "ephemeral_on_serve"
    assert seen == [LOCAL_DSN]
    assert "UNSAFE_PRIVATE_VALUE" not in json.dumps(result.as_dict())
    # CLI diagnostic must not reveal a DB auth secret under failures.
    assert "UNSAFE_PRIVATE_VALUE" not in capsys.readouterr().out


@pytest.mark.parametrize("dsn", [
    "", "sqlite:///tmp/ago.db", "postgresql://user:pass@evil.example.com/ago",
    "postgresql://user:pass@localhost/", "postgresql://u:p@127.0.0.1.evil/ago",
    "postgresql://u:p@localhost:notaport/ago", "https://localhost/ago",
])
def test_doctor_refuses_remote_and_malformed_dsns(local_environment, monkeypatch, dsn):
    monkeypatch.setenv("AGO_POSTGRES_DSN", dsn)
    called = []
    diag = local_ops.doctor(verify_schema=lambda *_: called.append(1) or True)
    assert not diag.ready
    assert not called


def test_doctor_checks_local_migration_mismatch_and_downgrades_to_not_ready(
    local_environment,
):
    assert not local_ops.doctor(verify_schema=lambda dsn: False).ready

    def fail(_dsn):
        raise RuntimeError("private password UNSAFE_PRIVATE_VALUE")

    assert not local_ops.doctor(verify_schema=fail).ready


def test_doctor_rejects_weak_secret_and_unsafe_prod_env(local_environment, monkeypatch):
    monkeypatch.setenv("AGO_SESSION_SECRET", "weak")
    assert not local_ops.doctor(verify_schema=lambda *_: True).ready
    monkeypatch.setenv("AGO_SESSION_SECRET", "valid-testing-session-secret-123456")
    assert local_ops.doctor(verify_schema=lambda *_: True).ready
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    called = []
    assert not local_ops.doctor(verify_schema=lambda *_: called.append(1) or True).ready
    assert called == []


def test_serve_only_listens_on_loopback_and_ephemeral_secret_is_not_saved(
    local_environment, monkeypatch, capsys,
):
    monkeypatch.setattr(local_ops, "doctor", lambda: local_ops.LocalDiagnosis(
        True, True, True, True, "ephemeral_on_serve", True,
    ))
    calls = []
    local_ops.serve_local(port=18765, run_server=lambda *a, **kw: calls.append((a, kw)))
    assert calls == [
        (("ago.main:app",), {"host": "127.0.0.1", "port": 18765, "reload": False}),
    ]
    assert len(os.environ["AGO_SESSION_SECRET"]) >= 48
    text = capsys.readouterr().out
    assert "127.0.0.1:18765/console/" in text
    assert os.environ["AGO_SESSION_SECRET"] not in text


def test_serve_fails_closed_without_schema_and_rejects_reserved_ports(
    local_environment, monkeypatch,
):
    monkeypatch.setattr(local_ops, "doctor", lambda: local_ops.LocalDiagnosis(
        True, True, True, False, "ephemeral_on_serve", False,
    ))
    called = []
    with pytest.raises(RuntimeError):
        local_ops.serve_local(run_server=lambda *a, **kw: called.append(1))
    with pytest.raises(ValueError):
        local_ops.serve_local(port=80, run_server=lambda *_a, **_kw: called.append(1))
    assert not called


def test_provision_rejects_duplicate_human_and_nonlocal_db_before_connection(
    local_environment, monkeypatch,
):
    base = {
        "organization": "AGO CI",
        "founder_email": "owner@example.test",
        "founder_password": "founder-password-123",
        "reviewer_email": "reviewer@example.test",
        "reviewer_password": "reviewer-password-123",
    }
    with pytest.raises(ValueError):
        local_ops.provision_pilot(
            **(base | {"reviewer_email": " OWNER@example.test "}),
            verify_schema=lambda *_: True,
        )
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    with pytest.raises(PermissionError):
        local_ops.provision_pilot(**base, verify_schema=lambda *_: True)
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://u:p@evil.example/ago")
    with pytest.raises(PermissionError):
        local_ops.provision_pilot(**base, verify_schema=lambda *_: True)


def test_provision_one_transaction_with_founder_and_reviewer(
    local_environment, monkeypatch,
):
    import ago.bootstrap
    import ago.provision

    order = []

    class FakeConnection:
        def __enter__(self):
            order.append("db-open")
            return self

        def __exit__(self, exc_type, *_):
            order.append("db-close")

        @contextlib.contextmanager
        def transaction(self):
            order.append("tx-open")
            try:
                yield self
            finally:
                order.append("tx-close")

    def connect(*a, **kwargs):
        assert a == (LOCAL_DSN,)
        assert kwargs["autocommit"]
        return FakeConnection()

    def bootstrap(db, *, organization, email, password):
        order.append("founder")
        assert (organization, email, password) == (
            "AGO CI", "owner@example.test", "founder-password-123",
        )
        return "tenant-id", "founder-id"

    def reviewer(db, *, tenant_id, email, password):
        assert tenant_id == "tenant-id"
        order.append("reviewer")
        return "reviewer-id"

    monkeypatch.setattr(ago.bootstrap, "bootstrap", bootstrap)
    monkeypatch.setattr(ago.provision, "add_reviewer", reviewer)
    result = local_ops.provision_pilot(
        organization="AGO CI", founder_email="owner@example.test",
        founder_password="founder-password-123",
        reviewer_email="reviewer@example.test",
        reviewer_password="reviewer-password-123",
        connector=connect, verify_schema=lambda dsn: True,
    )
    assert result == {
        "tenant_id": "tenant-id", "founder_id": "founder-id",
        "reviewer_id": "reviewer-id",
    }
    assert order == [
        "db-open", "tx-open", "founder", "reviewer", "tx-close", "db-close",
    ]


def test_interactive_cancellation_does_not_provision(
    local_environment, monkeypatch, capsys,
):
    monkeypatch.setattr(local_ops, "doctor", lambda: local_ops.LocalDiagnosis(
        True, True, True, True, "configured", True,
    ))
    answers = iter(["AGO CI", "owner@example.test",
                    "reviewer@example.test", "CANCEL"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    monkeypatch.setattr("getpass.getpass", lambda *_: "twelve-char-password")
    monkeypatch.setattr(local_ops, "provision_pilot", lambda **_: (_ for _ in ()).throw(
        AssertionError("This must never run without explicit CREATE consent"),
    ))
    assert local_ops.main(["init"]) == 2
    assert "Cancelled" in capsys.readouterr().out


def test_real_postgresql_onboarding_and_independent_approval(local_environment, monkeypatch):
    dsn = os.getenv("AGO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Disposable migrated AGO_TEST_POSTGRES_DSN required")
    # CI database host is localhost. Do not operate on a production DB.
    if not local_ops.local_database(dsn):
        pytest.skip("Only a local CI database can be used for this integration test")
    monkeypatch.setenv("AGO_POSTGRES_DSN", dsn)
    assert local_ops.doctor().ready
    unique = str(uuid4())[:12]
    result = local_ops.provision_pilot(
        organization="AGO M12 pilot " + unique,
        founder_email="founder-" + unique + "@example.test",
        founder_password="founder-secret-1234567",
        reviewer_email="reviewer-" + unique + "@example.test",
        reviewer_password="reviewer-secret-1234567",
    )
    from psycopg.rows import dict_row
    import psycopg

    with psycopg.connect(dsn, row_factory=dict_row) as db:
        rows = db.execute(
            """SELECT u.id,u.email,r.role
               FROM ago_users u
               JOIN ago_user_roles r ON r.tenant_id=u.tenant_id
                                   AND r.user_id=u.id
               WHERE u.tenant_id=%s ORDER BY r.role""",
            (result["tenant_id"],),
        ).fetchall()
        assert {r["role"] for r in rows} == {"founder", "reviewer"}
        assert len({str(r["id"]) for r in rows}) == 2

        # Failed reviewer creation must roll back new tenant and founder.
        original_count = db.execute(
            "SELECT count(*) AS n FROM ago_tenants"
        ).fetchone()["n"]
    with pytest.raises(ValueError):
        local_ops.provision_pilot(
            organization="AGO M12 failed pilot " + unique,
            founder_email="founder-rollback-" + unique + "@example.test",
            founder_password="founder-secret-1234567",
            reviewer_email="invalid-email",
            reviewer_password="reviewer-secret-1234567",
        )
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        after = db.execute(
            "SELECT count(*) AS n FROM ago_tenants"
        ).fetchone()["n"]
        assert after == original_count
