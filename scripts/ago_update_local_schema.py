"""Guarded backup-first schema refresh for the historical local ago_test database."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg

from ago.event_runtime import migrate
from ago.local_ops import local_database
from ago.release_ops import create_backup, verify_archive
from ago.release_security import schema_integrity

CONFIRM = "UPDATE_HISTORICAL_AGO_TEST"
REVIEWED_LAST = "061_board_handoff_blocker_reporting.sql"
CORE = ("ago_tenants", "ago_users", "ago_employees", "ago_strategy_plans",
        "ago_founder_intakes", "ago_governed_tasks", "ago_agent_runs",
        "ago_approval_requests")


class Blocked(RuntimeError):
    """A sanitized preflight failure."""


def validate_target(dsn: str) -> None:
    if os.getenv("AGO_ENVIRONMENT", "development") != "development":
        raise Blocked("development_only")
    if not local_database(dsn):
        raise Blocked("invalid_local_dsn")
    p = urlsplit(dsn)
    if (p.hostname != "127.0.0.1" or p.port not in (None, 5432)
            or unquote(p.path.lstrip("/")) != "ago_test"):
        raise Blocked("only_127_0_0_1_ago_test_allowed")


def migration_plan(sql_dir: Path, records: list[tuple[str, str]]) -> dict:
    files = sorted(sql_dir.glob("*.sql"))
    if not files or files[-1].name != REVIEWED_LAST:
        raise Blocked("unexpected_sql_migration_version")
    hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    stored = {}
    for name, sha in records:
        if name in stored:
            raise Blocked("duplicate_historical_migration")
        stored[name] = sha.lower()
    if not stored:
        raise Blocked("no_historical_ago_migrations")
    if any(name not in hashes for name in stored):
        raise Blocked("unexpected_applied_migration")
    if any(hashes[name] != digest for name, digest in stored.items()):
        raise Blocked("historical_migration_checksum_mismatch")
    return {
        "expected": len(hashes), "applied": len(stored),
        "latest": max(stored),
        "pending": [f.name for f in files if f.name not in stored],
    }


def snapshot(db) -> dict:
    name = db.execute("SELECT current_database()").fetchone()[0]
    tables = db.execute(
        "SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname='public'"
    ).fetchone()[0]
    counts = {}
    for table in CORE:  # constant allowlist; never user-supplied SQL identifiers
        exists = db.execute(
            "SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",)
        ).fetchone()[0]
        counts[table] = (db.execute(f"SELECT COUNT(*) FROM public.{table}")
                         .fetchone()[0] if exists else "absent")
    return {"name": name, "public_tables": tables, "counts": counts}


def read_state(dsn: str, sql_dir: Path) -> tuple[dict, dict]:
    with psycopg.connect(dsn, connect_timeout=5,
                         options="-c default_transaction_read_only=on") as db:
        if db.execute("SELECT current_database()").fetchone()[0] != "ago_test":
            raise Blocked("wrong_connected_database")
        exists = db.execute(
            "SELECT to_regclass('public.ago_schema_migrations') IS NOT NULL"
        ).fetchone()[0]
        if not exists:
            raise Blocked("historical_migration_ledger_missing")
        records = db.execute(
            "SELECT filename,sha256 FROM public.ago_schema_migrations ORDER BY filename"
        ).fetchall()
        return migration_plan(sql_dir, records), snapshot(db)


def execute(dsn: str, sql_dir: Path, backup_dir: Path, *, apply=False,
            confirm="") -> dict:
    validate_target(dsn)
    plan, before = read_state(dsn, sql_dir)
    result = {"database": "ago_test", "mode": "read_only" if not apply else "upgrade",
              "migration_plan": plan, "before": before}
    if not apply:
        return result
    if confirm != CONFIRM:
        raise Blocked("explicit_confirmation_required")
    if not plan["pending"]:
        if not schema_integrity(dsn, sql_dir):
            raise Blocked("schema_checksum_validation_failed")
        result.update({"status": "already_current", "ready_schema": True})
        return result
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive = backup_dir / f"ago_test-pre-upgrade-{stamp}.dump"
    backup = create_backup(dsn, archive, confirmed=True)
    verify_archive(archive)
    result["verified_backup"] = {"path": str(archive), "bytes": backup["bytes"],
                                 "sha256": backup["sha256"]}
    # Existing runner validates historical digests, holds an advisory lock, and
    # applies all new SQL files in a single transaction.
    applied = migrate(dsn, sql_dir)
    if not schema_integrity(dsn, sql_dir):
        raise Blocked("schema_not_current_after_upgrade")
    final_plan, after = read_state(dsn, sql_dir)
    if final_plan["pending"]:
        raise Blocked("migration_ledger_still_incomplete")
    result.update({"status": "updated", "applied_now": applied,
                   "migration_plan_after": final_plan, "after": after,
                   "ready_schema": True})
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--backup-dir", default=str(
        Path(os.getenv("LOCALAPPDATA") or Path.home()) / "AGO" / "backups"))
    args = ap.parse_args(argv)
    try:
        report = execute(
            os.getenv("AGO_POSTGRES_DSN", ""),
            Path(__file__).resolve().parents[1] / "deploy" / "sql",
            Path(args.backup_dir), apply=args.apply, confirm=args.confirm,
        )
        print(json.dumps(report, sort_keys=True))
        return 0
    except Blocked as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
    except (psycopg.Error, OSError, RuntimeError, ValueError, KeyError) as exc:
        # Never print raw DSNs, PostgreSQL errors or credentials.
        print(json.dumps({"status": "blocked", "reason": "operator_action_failed",
                          "error_type": type(exc).__name__}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
