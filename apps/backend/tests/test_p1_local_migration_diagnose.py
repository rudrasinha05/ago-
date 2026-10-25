"""Read-only migration diagnostics are safe even with private DSN values."""
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "scripts" / "ago_local_migration_diagnose.py"
SPEC = spec_from_file_location("ago_migration_diagnosis_test", SOURCE)
module = module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Rows:
    def __init__(self, content):
        self.content = content
    def fetchone(self):
        return self.content
    def fetchall(self):
        return self.content


class FakePostgres:
    def __init__(self, rows=(), table=True):
        self.rows = rows
        self.table = table
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql):
        self.calls.append(sql)
        assert (sql == "SET TRANSACTION READ ONLY"
                or sql.startswith("SELECT "))
        if "to_regclass" in sql:
            return Rows(("ago_schema_migrations" if self.table else None,))
        return Rows(self.rows)


def test_read_only_migration_match_reports_correct_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://u:PRIVATE_SECRET@127.0.0.1/ago")
    (tmp_path / "001.sql").write_text("SELECT 1;", encoding="utf-8")
    import hashlib
    digest = hashlib.sha256((tmp_path / "001.sql").read_bytes()).hexdigest()
    conn = FakePostgres(rows=[("001.sql", digest)])
    report = module.diagnose(connector=lambda *_a, **_k: conn, directory=tmp_path)
    assert report["schema_integrity"]
    assert report["connection"] == "connected"
    assert report["database_modified"] is False
    assert len(conn.calls) == 3
    assert all("PRIVATE_SECRET" not in str(item) for item in report.values())


def test_checksum_mismatch_and_missing_are_visible(monkeypatch, tmp_path):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://u:secret@localhost/ago")
    for name in ("001.sql", "002.sql"):
        (tmp_path / name).write_text("SELECT 1;", encoding="utf-8")
    conn = FakePostgres(rows=[("001.sql", "old-digest"), ("extra.sql", "x")])
    report = module.diagnose(connector=lambda *_a, **_k: conn, directory=tmp_path)
    assert not report["schema_integrity"]
    assert report["missing_in_database"] == ["002.sql"]
    assert report["changed_checksum"] == ["001.sql"]
    assert report["extra_in_database"] == ["extra.sql"]


def test_missing_tracking_table_is_not_auto_created(monkeypatch, tmp_path):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://u:secret@localhost/ago")
    (tmp_path / "001.sql").write_text("SELECT 1;", encoding="utf-8")
    conn = FakePostgres(table=False)
    result = module.diagnose(connector=lambda *_a, **_k: conn, directory=tmp_path)
    assert result["tracking_table"] == "missing"
    assert not result["schema_integrity"]
    assert len(conn.calls) == 2


@pytest.mark.parametrize("dsn,stage", [
    ("postgresql://u:p@remote.example/ago", "development"),
    ("postgresql://u:p@127.0.0.1/ago", "production"),
    ("", "development"),
])
def test_unsafe_target_never_connects(monkeypatch, tmp_path, dsn, stage):
    monkeypatch.setenv("AGO_ENVIRONMENT", stage)
    monkeypatch.setenv("AGO_POSTGRES_DSN", dsn)
    def blocked(*_a, **_kw):
        raise AssertionError("Must not connect to unsafe target")
    report = module.diagnose(connector=blocked, directory=tmp_path)
    assert report["connection"] == "not_attempted"
    assert not report["database_modified"]


def test_connection_errors_never_leak_private_value(monkeypatch, tmp_path):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_POSTGRES_DSN", "postgresql://u:SECRET_VALUE@localhost/ago")
    (tmp_path / "001.sql").write_text("SELECT 1;", encoding="utf-8")
    def refused(*_a, **_kw):
        raise RuntimeError("password SECRET_VALUE invalid")
    result = module.diagnose(connector=refused, directory=tmp_path)
    assert result["connection"] == "failed"
    assert result["error_type"] == "RuntimeError"
    assert "SECRET_VALUE" not in str(result)
