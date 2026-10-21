"""AGO local-only, founder-started, non-replaying stale agent-run recovery.

Default: dry-run only. Opt-in --apply requires exact confirmation.
Never creates jobs, reruns external side effects, starts a service, wakes the
laptop, calls a model, or changes approvals. Ctrl+C terminates watch mode.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from time import sleep
from uuid import UUID

from ago.local_ops import local_database

CONFIRM="MARK_STALE_FAILED"
STATES=frozenset(("development","test","testing"))


def validate_local(dsn: str, environment: str, tenant_id: str,
                   min_age: int, *, apply: bool, confirm: str | None) -> str:
    tenant=str(UUID(tenant_id))
    if environment.strip().lower() not in STATES or not local_database(dsn):
        raise PermissionError("Founder-started local development/test PostgreSQL only")
    if not 3600<=min_age<=604800:
        raise ValueError("Recovery cutoff must be between 1 hour and 7 days")
    if apply and confirm!=CONFIRM:
        raise PermissionError("Exact founder confirmation required")
    return tenant


def count_stale(db, tenant: str, min_age: int) -> int:
    row=db.execute("""
        SELECT COUNT(*) AS total FROM ago_agent_runs
        WHERE tenant_id=%s AND status='running'
          AND started_at < now()-(%s * interval '1 second')
    """,(tenant,min_age)).fetchone()
    return int(row["total"])


def reconcile(db, tenant: str, min_age: int, *, apply: bool) -> dict:
    pending=count_stale(db,tenant,min_age)
    updated=0
    if apply:
        from ago.agent_runtime import AgentRuntime
        # Existing recovery only marks abandoned runs/tasks as FAILED.
        # External effects are never retried and no approval is fabricated.
        # Each bounded transaction re-checks status with SKIP LOCKED.
        for _ in range(10):
            batch=AgentRuntime(db).recover_stale(
                tenant_id=tenant,minimum_age_seconds=min_age)
            updated+=batch
            if batch<100:
                break
    return {
        "tenant_id":tenant,"checked_at":datetime.now(timezone.utc).isoformat(),
        "mode":"mark_failed_without_replay" if apply else "read_only",
        "observed_stale_runs":pending,"marked_failed":updated,
        "external_actions_replayed":False,
        "requires_manual_investigation":updated>0 or pending>0,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id",required=True)
    parser.add_argument("--min-age-seconds",type=int,default=3600)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--watch",action="store_true")
    parser.add_argument("--interval-seconds",type=int,default=600)
    args=parser.parse_args(argv)
    if args.watch and not args.apply:
        parser.error("Watch mode needs explicit --apply and confirmation")
    if not 300<=args.interval_seconds<=3600:
        parser.error("Polling interval must be 300–3600 seconds")
    try:
        tenant=validate_local(
            os.getenv("AGO_POSTGRES_DSN",""),
            os.getenv("AGO_ENVIRONMENT","development"),
            args.tenant_id,args.min_age_seconds,
            apply=args.apply,confirm=args.confirm)
    except (PermissionError,ValueError) as exc:
        parser.error(str(exc))
    import psycopg
    from psycopg.rows import dict_row
    while True:
        try:
            with psycopg.connect(os.environ["AGO_POSTGRES_DSN"],
                                connect_timeout=5,row_factory=dict_row,
                                autocommit=True) as db:
                outcome=reconcile(db,tenant,args.min_age_seconds,apply=args.apply)
            print(json.dumps(outcome,sort_keys=True),flush=True)
        except psycopg.Error:
            print(json.dumps({"status":"local_db_unavailable",
                "external_actions_replayed":False}),flush=True)
            if not args.watch:
                return 2
        if not args.watch:
            return 0
        try:
            sleep(args.interval_seconds)
        except KeyboardInterrupt:
            return 0


if __name__=="__main__":
    raise SystemExit(main())
