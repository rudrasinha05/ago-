"""Read-only, credential-redacted local PostgreSQL migration comparison.

This command NEVER applies migrations, creates tables, resets state or changes
SQL data. Run manually from the AGO repository root; stdout contains no DSN,
SQL error detail, project data, usernames or credentials.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "apps" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ago.event_runtime import migration_directory  # noqa: E402
from ago.local_ops import local_database  # noqa: E402


def compare_migrations(expected: dict[str, str], recorded: dict[str, str]) -> dict:
    """Return safe names only; do not modify or conceal changed hashes."""
    return {
        "missing_in_database": sorted(expected.keys() - recorded.keys()),
        "changed_checksum": sorted(
            name for name in expected.keys() & recorded.keys()
            if expected[name] != recorded[name]
        ),
        "extra_in_database": sorted(recorded.keys() - expected.keys()),
    }


def diagnose(*, connector=None, directory: Path | None = None) -> dict:
    """Compare local SQL files to tracking rows using SELECT-only PostgreSQL."""
    dsn = os.getenv("AGO_POSTGRES_DSN", "").strip()
    local_stage = os.getenv("AGO_ENVIRONMENT", "development").lower() in {
        "development", "test", "testing",
    }
    report = {
        "kind": "ago_local_migration_readonly_diagnosis",
        "stage_safe": local_stage,
        "database_configured": bool(dsn),
        "database_local": local_database(dsn),
        "connection": "not_attempted",
        "tracking_table": "not_checked",
        "expected_file_count": 0,
        "recorded_file_count": None,
        "missing_in_database": [],
        "changed_checksum": [],
        "extra_in_database": [],
        "schema_integrity": False,
        "database_modified": False,
    }
    if not (report["stage_safe"] and report["database_local"]):
        return report
    folder = directory or migration_directory()
    files = sorted(folder.glob("*.sql")) if folder.is_dir() else []
    expected = {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                for file in files}
    report["expected_file_count"] = len(expected)
    if not files:
        report["migration_directory"] = "missing_or_empty"
        return report
    try:
        if connector is None:
            import psycopg
            connector = psycopg.connect
        with connector(dsn, connect_timeout=3) as db:
            db.execute("SET TRANSACTION READ ONLY")
            exists = db.execute("SELECT to_regclass('ago_schema_migrations')").fetchone()
            report["connection"] = "connected"
            if not exists or exists[0] is None:
                report["tracking_table"] = "missing"
                report["missing_in_database"] = sorted(expected)
                return report
            report["tracking_table"] = "present"
            rows = db.execute(
                "SELECT filename,sha256 FROM ago_schema_migrations"
            ).fetchall()
        recorded = {str(row[0]): str(row[1]) for row in rows}
        report["recorded_file_count"] = len(recorded)
        report.update(compare_migrations(expected, recorded))
        report["schema_integrity"] = not any(report[key] for key in (
            "missing_in_database", "changed_checksum", "extra_in_database",
        ))
    except Exception as exc:
        # PostgreSQL exceptions can contain passwords, hostnames, query data.
        # Disclose only the class name; never repr(exc), traceback or DSN.
        report["connection"] = "failed"
        report["error_type"] = type(exc).__name__
    return report


def main() -> int:
    result = diagnose()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["schema_integrity"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
