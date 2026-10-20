"""Local observer reliability; no PostgreSQL instance or network needed."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "opportunity_scan.py"
SPEC = spec_from_file_location("ago_opportunity_observer", SCRIPT)
observer = module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


def test_once_success_keeps_machine_readable_report(monkeypatch, capsys):
    monkeypatch.setattr(observer, "scan_once", lambda dsn, tenant: {
        "created": 3, "reason": "idle_hypotheses_proposed", "opportunities": [],
    })
    tenant = str(uuid4())
    assert observer.watch(tenant_id=tenant, dsn="localhost", once=True, interval_seconds=3600) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ok"
    assert report["created"] == 3
    assert report["tenant_id"] == tenant
    assert report["checked_at"]


def test_once_outage_returns_nonzero_and_does_not_log_secrets(monkeypatch, capsys):
    def offline(*_args):
        raise psycopg.OperationalError("password=do-not-log-any-credential")

    monkeypatch.setattr(observer, "scan_once", offline)
    result = observer.watch(
        tenant_id=str(uuid4()), dsn="postgresql://user:secret@localhost/db",
        once=True, interval_seconds=3600,
    )
    output = capsys.readouterr().out
    report = json.loads(output)
    assert result == 1
    assert report["status"] == "degraded"
    assert report["error_type"] == "OperationalError"
    assert report["created"] == 0
    assert "secret" not in output
    assert "do-not-log" not in output


def test_watch_recovers_after_transient_outage(monkeypatch, capsys):
    calls = []
    sleeps = []

    class StopObserver(Exception):
        pass

    def scan(*_args):
        calls.append(True)
        if len(calls) == 1:
            raise psycopg.OperationalError("temporary database connection error")
        return {"created": 0, "reason": "already_proposed_this_month", "opportunities": []}

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopObserver

    monkeypatch.setattr(observer, "scan_once", scan)
    monkeypatch.setattr(observer.time, "sleep", sleep)
    with pytest.raises(StopObserver):
        observer.watch(
            tenant_id=str(uuid4()), dsn="localhost", once=False, interval_seconds=3600,
        )
    reports = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [r["status"] for r in reports] == ["degraded", "ok"]
    assert sleeps == [60, 3600]
    assert len(calls) == 2


def test_production_and_nonlocal_databases_fail_closed(monkeypatch):
    tenant = str(uuid4())
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://user@localhost/ago_test")
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    with pytest.raises(SystemExit) as exc:
        observer.main(["--tenant-id", tenant, "--once"])
    assert exc.value.code == 2
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://user@remote.example/ago")
    with pytest.raises(SystemExit) as exc:
        observer.main(["--tenant-id", tenant, "--once"])
    assert exc.value.code == 2
