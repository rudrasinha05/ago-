from pathlib import Path

import pytest

from ago.local_ops import local_database


def test_upgrade_source_contract():
    src = Path(__file__).resolve().parents[3] / "scripts" / "ago_update_local_schema.py"
    contents = src.read_text(encoding="utf-8")
    compile(contents, str(src), "exec")
    assert "create_backup(dsn, archive, confirmed=True)" in contents
    assert "verify_archive(archive)" in contents


def test_historical_dsn_and_ledger(tmp_path, monkeypatch):
    import runpy
    src = Path(__file__).resolve().parents[3] / "scripts" / "ago_update_local_schema.py"
    module = runpy.run_path(str(src), run_name="ago_schema_helper_test")
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    check = module["validate_target"]
    assert local_database("postgresql://user:secret@127.0.0.1:5432/ago_test")
    check("postgresql://user:secret@127.0.0.1:5432/ago_test")
    with pytest.raises(module["Blocked"]):
        check("postgresql://user:secret@127.0.0.1:5432/ago_dev")
    with pytest.raises(module["Blocked"]):
        check("postgresql://user:secret@remote.example.com:5432/ago_test")

    p = tmp_path / "deploy"
    p.mkdir()
    a = p / "060_test.sql"
    b = p / "061_board_handoff_blocker_reporting.sql"
    a.write_text("SELECT 1")
    b.write_text("SELECT 2")
    import hashlib
    record = [(a.name, hashlib.sha256(a.read_bytes()).hexdigest())]
    plan = module["migration_plan"](p, record)
    assert plan["applied"] == 1
    assert plan["pending"] == [b.name]
    with pytest.raises(module["Blocked"]):
        module["migration_plan"](p, [(a.name, "bad-hash")])
    with pytest.raises(module["Blocked"]):
        module["migration_plan"](p, [(a.name, record[0][1]), ("bad.sql", "1")])
