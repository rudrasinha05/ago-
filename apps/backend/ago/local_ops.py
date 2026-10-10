"""M12 local-only AGO doctor, guarded founder onboarding and server launcher.

Examples from apps/backend (with AGO_POSTGRES_DSN in environment):
    python -m ago.local_ops doctor
    python -m ago.local_ops init
    python -m ago.local_ops serve

No credentials written to disk, no implicit migrations and no browser-run
operations from this CLI. A fresh reviewer is another real human, never AI.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit

from ago.release_security import schema_integrity

_LOCAL_STAGES = frozenset(("development", "test", "testing"))
_LOCAL_DB_HOSTS = frozenset(("localhost", "127.0.0.1", "::1"))


@dataclass(frozen=True)
class LocalDiagnosis:
    stage_safe: bool
    database_configured: bool
    database_local: bool
    migrations_applied: bool
    signing_secret: str
    ready: bool

    def as_dict(self) -> dict:
        return {
            "stage_safe": self.stage_safe,
            "database_configured": self.database_configured,
            "database_local": self.database_local,
            "migrations_applied": self.migrations_applied,
            "signing_secret": self.signing_secret,
            "ready": self.ready,
        }


def _stage() -> str:
    return os.getenv("AGO_ENVIRONMENT", "development").strip().lower()


def _dsn() -> str:
    return os.getenv("AGO_POSTGRES_DSN", "").strip()


def local_database(dsn: str) -> bool:
    """Local operator operations refuse remote or ambiguous SQL connections."""
    if not dsn:
        return False
    try:
        parsed = urlsplit(dsn)
        port = parsed.port  # Access eagerly: a malformed port raises ValueError.
        return (
            parsed.scheme in ("postgres", "postgresql")
            and parsed.hostname in _LOCAL_DB_HOSTS
            and (port is None or 1 <= port <= 65535)
            and bool(parsed.path.strip("/"))
            and bool(parsed.username)
            and not parsed.fragment
        )
    except ValueError:
        return False


def doctor(*, verify_schema=schema_integrity) -> LocalDiagnosis:
    """Read-only check; never print DSN, secrets, usernames or DB stack traces."""
    stage_safe = _stage() in _LOCAL_STAGES
    dsn = _dsn()
    configured = bool(dsn)
    db_local = local_database(dsn)
    secret = os.getenv("AGO_SESSION_SECRET", "")
    if not secret:
        secret_state = "ephemeral_on_serve"
    elif len(secret.encode("utf-8")) >= 32:
        secret_state = "configured"
    else:
        secret_state = "too_short"
    migrated = False
    if stage_safe and configured and db_local:
        try:
            migrated = bool(verify_schema(dsn))
        except Exception:
            migrated = False
    ready = (stage_safe and configured and db_local and migrated
             and secret_state != "too_short")
    return LocalDiagnosis(
        stage_safe, configured, db_local, migrated, secret_state, ready,
    )


def provision_pilot(
    *, organization: str, founder_email: str, founder_password: str,
    reviewer_email: str, reviewer_password: str,
    connector=None, verify_schema=schema_integrity,
) -> dict[str, str]:
    """Create tenant plus two real human accounts in a single DB transaction.

    Existing tenants are never updated. If reviewer creation fails, founder
    and new tenant roll back as well. Only a localhost development/test DB.
    """
    if _stage() not in _LOCAL_STAGES:
        raise PermissionError("Local setup cannot run in staging or production")
    dsn = _dsn()
    if not local_database(dsn):
        raise PermissionError("Local setup requires a localhost PostgreSQL database")
    if (
        not organization.strip()
        or not founder_email.strip() or not reviewer_email.strip()
        or founder_email.strip().lower() == reviewer_email.strip().lower()
    ):
        raise ValueError("Organization and two different human emails are required")
    if len(founder_password) < 12 or len(reviewer_password) < 12:
        raise ValueError("Both passwords require at least 12 characters")
    if not verify_schema(dsn):
        raise RuntimeError("Database migrations are not current; apply explicitly first")
    from psycopg.rows import dict_row
    import psycopg

    from ago.bootstrap import bootstrap
    from ago.provision import add_reviewer

    connect = connector or psycopg.connect
    with connect(dsn, row_factory=dict_row, autocommit=True, connect_timeout=3) as db:
        with db.transaction():
            tenant_id, founder_id = bootstrap(
                db, organization=organization.strip(),
                email=founder_email.strip(), password=founder_password,
            )
            reviewer_id = add_reviewer(
                db, tenant_id=tenant_id,
                email=reviewer_email.strip(), password=reviewer_password,
            )
    return {
        "tenant_id": tenant_id,
        "founder_id": founder_id,
        "reviewer_id": reviewer_id,
    }


def serve_local(*, port: int = 8000, run_server=None) -> None:
    """Refuse unsafe startup; run loopback Uvicorn only, no implicit SQL writes."""
    if not 1024 <= port <= 65535:
        raise ValueError("Port must be between 1024 and 65535")
    diagnosis = doctor()
    if not diagnosis.ready:
        raise RuntimeError("AGO doctor failed; fix local DB/schema/environment first")
    if diagnosis.signing_secret == "ephemeral_on_serve":
        os.environ["AGO_SESSION_SECRET"] = secrets.token_urlsafe(48)
        print("Development-only signing secret generated in process memory.")
        print("Restarting this server will invalidate prior browser sessions.")
    import uvicorn

    runner = run_server or uvicorn.run
    print(f"AGO Control Center: http://127.0.0.1:{port}/console/")
    print(f"Health: http://127.0.0.1:{port}/health/ready")
    runner("ago.main:app", host="127.0.0.1", port=port, reload=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AGO safe local operator workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Read-only environment and schema checks")
    sub.add_parser("init", help="Create new organization, founder and reviewer")
    server = sub.add_parser("serve", help="Launch localhost Control Center")
    server.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "doctor":
        info = doctor().as_dict()
        print(json.dumps(info, sort_keys=True))
        return 0 if info["ready"] else 2
    try:
        if args.command == "serve":
            serve_local(port=args.port)
            return 0
        diagnosis = doctor()
        if not diagnosis.ready:
            raise RuntimeError("Doctor must pass before creating a tenant")
        print("Creates ONE new local organization and TWO distinct human accounts.")
        print("No existing organization or user is overwritten.")
        organization = input("Organization name: ").strip()
        founder_email = input("Founder email: ").strip()
        founder_password = getpass.getpass("Founder password (min 12 chars): ")
        reviewer_email = input("Independent human reviewer email: ").strip()
        reviewer_password = getpass.getpass("Reviewer password (min 12 chars): ")
        acknowledgement = input("Type CREATE to confirm new tenant: ").strip()
        if acknowledgement != "CREATE":
            print("Cancelled; no tenant was created.")
            return 2
        records = provision_pilot(
            organization=organization, founder_email=founder_email,
            founder_password=founder_password,
            reviewer_email=reviewer_email,
            reviewer_password=reviewer_password,
        )
        print(json.dumps(records, sort_keys=True))
        print("Save tenant_id privately; it is required for browser sign-in.")
        return 0
    except (ValueError, PermissionError, RuntimeError, OSError, ImportError):
        print("Operation did not complete. Check local environment and doctor.")
        # Never echo database DSN, password, internal connection error or secret.
        return 2


if __name__ == "__main__":
    sys.exit(main())
