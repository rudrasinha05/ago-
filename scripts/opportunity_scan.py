"""Trusted local opportunity watcher: monitored retries, no outreach or spending.

From apps/backend:
  python ../../scripts/opportunity_scan.py --tenant-id UUID --once
  python ../../scripts/opportunity_scan.py --tenant-id UUID --interval-seconds 3600

Only operates against configured local development/test PostgreSQL. This
process is not a hosted 24/7 agent and cannot run when the computer is off.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import time
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ago.company_chat import CompanyChat
from ago.local_ops import local_database


def scan_once(dsn: str, tenant_id: str) -> dict:
    """Create only durable, idempotent founder-review hypotheses for this tenant."""
    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True, connect_timeout=5) as db:
        return CompanyChat(db).scan_opportunities(tenant_id)


def watch(*, tenant_id: str, dsn: str, once: bool, interval_seconds: int) -> int:
    """Keep observing after transient DB failures; never disguise them as successful scans."""
    while True:
        degraded = False
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            report = scan_once(dsn, tenant_id)
            print(json.dumps({
                **report, "status": "ok", "checked_at": timestamp, "tenant_id": tenant_id,
            }, sort_keys=True), flush=True)
        except (psycopg.Error, OSError) as exc:
            degraded = True
            # Exception messages may contain a full DSN, host or username: do not log them.
            print(json.dumps({
                "status": "degraded",
                "checked_at": timestamp,
                "tenant_id": tenant_id,
                "error_type": type(exc).__name__,
                "sqlstate": getattr(exc, "sqlstate", None),
                "created": 0,
            }, sort_keys=True), flush=True)
        if once:
            return 1 if degraded else 0
        time.sleep(min(interval_seconds, 60) if degraded else interval_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AGO local idle-company opportunity watcher")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    tenant_id = str(UUID(args.tenant_id))
    if not 300 <= args.interval_seconds <= 86400:
        parser.error("Polling interval must be between 300 and 86400 seconds")
    dsn = os.getenv("AGO_POSTGRES_DSN", "")
    if (
        os.getenv("AGO_ENVIRONMENT", "development") not in ("development", "test", "testing")
        or not local_database(dsn)
    ):
        parser.error("Only configured localhost development/test PostgreSQL is supported")
    return watch(
        tenant_id=tenant_id, dsn=dsn,
        once=args.once, interval_seconds=args.interval_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
