from pathlib import Path

import pytest

from ago.event_migrations import MigrationError, apply_migrations


def test_missing_migration_directory(tmp_path):
    with pytest.raises(MigrationError, match="missing"):
        apply_migrations(None, tmp_path / "missing")


def test_migration_checksum_and_order(tmp_path):
    class Connection:
        def __init__(self):
            self.applied = {}
            self.statements = []

        def transaction(self):
            from contextlib import nullcontext
            return nullcontext()

        def execute(self, sql, params=None):
            self.statements.append(sql)
            if sql.startswith("SELECT filename"):
                return self
            if sql.startswith("INSERT INTO ago_schema_migrations"):
                self.applied[params[0]] = params[1]
            return self

        def fetchall(self):
            return list(self.applied.items())

    (tmp_path / "002_second.sql").write_text("SELECT 2")
    (tmp_path / "001_first.sql").write_text("SELECT 1")
    db = Connection()
    assert apply_migrations(db, Path(tmp_path)) == ["001_first.sql", "002_second.sql"]
    assert apply_migrations(db, Path(tmp_path)) == []
    (tmp_path / "001_first.sql").write_text("SELECT 3")
    with pytest.raises(MigrationError, match="changed"):
        apply_migrations(db, Path(tmp_path))
