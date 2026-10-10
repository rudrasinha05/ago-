"""M10 deliberate operator commands: preflight, backup, integrity and restore drill.

All mutations require explicit flags. pg_dump/pg_restore are subprocess arg
arrays (never shell). No password/DSN is printed in reports or command lines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from ago.release_security import ReleasePolicy, schema_integrity


def _connection_parts(dsn: str) -> tuple[dict, dict]:
    try:
        parsed = urlsplit(dsn)
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError("Only PostgreSQL URI connection strings are accepted")
        host = parsed.hostname
        database = unquote(parsed.path.lstrip("/"))
        if not host or not database or not parsed.username:
            raise ValueError("PostgreSQL hostname, database and user required")
        port = parsed.port or 5432
        username = unquote(parsed.username)
        password = unquote(parsed.password or "")
        params = parse_qs(parsed.query)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid PostgreSQL connection configuration") from exc
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    for uri_key, env_key in (("sslmode", "PGSSLMODE"),
                             ("sslrootcert", "PGSSLROOTCERT")):
        if uri_key in params:
            env[env_key] = params[uri_key][0]
    return {
        "host": host, "port": str(port), "user": username,
        "database": database,
    }, env


def _pg_args(parts: dict) -> list[str]:
    return ["--host", parts["host"], "--port", parts["port"],
            "--username", parts["user"], "--dbname", parts["database"]]


def check_release() -> dict:
    """Redacted machine-readable report. No DSN, passwords, secrets or file paths."""
    report = {"configuration": False, "schema": False,
              "external_egress_disabled": False, "passed": False}
    try:
        if os.getenv("AGO_ENVIRONMENT") != "production":
            return report
        policy = ReleasePolicy.from_environment()
        report["configuration"] = policy.production
        report["external_egress_disabled"] = (
            os.getenv("AGO_M8_EXTERNAL_ENABLED") != "true" and
            os.getenv("AGO_ENABLE_PAID_MODELS") != "true"
        )
        report["schema"] = schema_integrity(os.environ["AGO_POSTGRES_DSN"])
    except Exception:
        # Never propagate DB connection parameters into terminal/CI reports.
        pass
    report["passed"] = all((
        report["configuration"], report["schema"],
        report["external_egress_disabled"],
    ))
    return report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(archive: Path, manifest: Path | None = None) -> dict:
    archive = Path(archive)
    manifest = Path(manifest or archive.with_suffix(archive.suffix + ".manifest.json"))
    if not archive.is_file() or not manifest.is_file():
        raise ValueError("Backup archive and manifest required")
    if archive.is_symlink() or manifest.is_symlink():
        raise ValueError("Backup symlinks are forbidden")
    if archive.stat().st_size < 6:
        raise ValueError("Backup is empty")
    with archive.open("rb") as stream:
        if stream.read(5) != b"PGDMP":
            raise ValueError("Archive must be PostgreSQL custom format")
    details = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(details, dict) or details.get("format") != "pg-custom-v1"
            or details.get("bytes") != archive.stat().st_size
            or details.get("sha256") != _sha256(archive)):
        raise ValueError("Archive manifest verification failed")
    return {"verified": True, "sha256": details["sha256"],
            "bytes": details["bytes"]}


def create_backup(dsn: str, output: Path, *, confirmed: bool = False,
                  runner=subprocess.run) -> dict:
    if not confirmed:
        raise PermissionError("Backup requires explicit operator consent")
    parts, env = _connection_parts(dsn)
    output = Path(output)
    if output.is_symlink():
        raise ValueError("Output symlinks are not allowed")
    manifest = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or manifest.exists():
        raise FileExistsError("Backup and manifest must not already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve an exclusive path, prevent clobber, protect at-rest permissions.
    with output.open("xb") as handle:
        os.chmod(output, 0o600)
        handle.write(b"")
    try:
        result = runner(
            ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
             "--file", str(output), *_pg_args(parts)],
            env=env, capture_output=True, check=False, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError("Database dump failed; inspect privileged operator logs")
        if output.stat().st_size < 6:
            raise RuntimeError("Database dump did not produce a valid archive")
        with output.open("rb") as stream:
            if stream.read(5) != b"PGDMP":
                raise RuntimeError("Database dump is not a custom-format archive")
        record = {
            "format": "pg-custom-v1",
            "sha256": _sha256(output),
            "bytes": output.stat().st_size,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        with manifest.open("x", encoding="utf-8") as handle:
            os.chmod(manifest, 0o600)
            json.dump(record, handle, indent=2)
        return verify_archive(output, manifest)
    except Exception:
        output.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        raise


def restore_drill(
    source_dsn: str, target_dsn: str, archive: Path, *,
    confirmed: bool = False, runner=subprocess.run, connect=None,
) -> dict:
    if not confirmed:
        raise PermissionError("Restore drill requires explicit operator consent")
    source, _ = _connection_parts(source_dsn)
    target, env = _connection_parts(target_dsn)
    if (
        not target["database"].endswith("_restore_drill")
        or target["database"] == source["database"]
        or (target["host"], target["port"], target["database"]) ==
           (source["host"], source["port"], source["database"])
    ):
        raise PermissionError("Only a separate *_restore_drill database is permitted")
    verification = verify_archive(Path(archive))
    import psycopg
    if connect is None:
        connect = psycopg.connect
    with connect(target_dsn, connect_timeout=3) as db:
        existing = db.execute(
            """SELECT 1 FROM information_schema.tables
               WHERE table_schema='public' AND table_type='BASE TABLE' LIMIT 1"""
        ).fetchone()
        if existing is not None:
            raise PermissionError("Restore drill target must have an empty public schema")
    listed = runner(
        ["pg_restore", "--list", str(archive)],
        env=env, capture_output=True, check=False, timeout=30,
    )
    if listed.returncode != 0:
        raise RuntimeError("pg_restore cannot inspect backup archive")
    restored = runner(
        ["pg_restore", "--exit-on-error", "--single-transaction",
         "--no-owner", "--no-privileges", *_pg_args(target), str(archive)],
        env=env, capture_output=True, check=False, timeout=300,
    )
    if restored.returncode != 0:
        raise RuntimeError("Restore drill failed; discard drill database")
    if not schema_integrity(target_dsn):
        raise RuntimeError("Restored schema does not match source migrations")
    return {"restored": True, "schema_verified": True,
            "sha256": verification["sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="AGO controlled release operations")
    actions = parser.add_subparsers(dest="operation", required=True)
    actions.add_parser("check", help="Validate production config and schema (no secrets)")
    backup = actions.add_parser("backup")
    backup.add_argument("--output", required=True)
    backup.add_argument("--confirm", action="store_true")
    verify = actions.add_parser("verify-backup")
    verify.add_argument("--archive", required=True)
    drill = actions.add_parser("restore-drill")
    drill.add_argument("--archive", required=True)
    drill.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "check":
            report = check_release()
            print(json.dumps(report, sort_keys=True))
            if not report["passed"]:
                sys.exit(2)
            return
        if args.operation == "verify-backup":
            result = verify_archive(Path(args.archive))
        elif args.operation == "backup":
            result = create_backup(
                os.environ["AGO_POSTGRES_DSN"], Path(args.output),
                confirmed=args.confirm,
            )
        else:
            result = restore_drill(
                os.environ["AGO_POSTGRES_DSN"],
                os.environ["AGO_RESTORE_TEST_DSN"], Path(args.archive),
                confirmed=args.confirm,
            )
        print(json.dumps(result, sort_keys=True))
    except (ValueError, PermissionError, FileNotFoundError,
            FileExistsError, KeyError, RuntimeError, OSError):
        # No exception string may include connection DSNs/provider stderr.
        print(json.dumps({"passed": False, "error": "operator_action_failed"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
