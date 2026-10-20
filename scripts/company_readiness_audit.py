"""Safe read-only company acceptance pulse for local AGO operators.

Run from apps/backend:
  python ../../scripts/company_readiness_audit.py --tenant-id <UUID>

This reports evidence and blockers; it neither issues approvals nor
modifies schema, accounts, personnel or tasks. Exit 0 only with no blockers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ago.local_ops import local_database

REQUIRED_MIGRATION = "055_continuous_market_intelligence.sql"
MAX_SCAN_AGE_SECONDS = 7200
STALLED_TASK_AGE_HOURS = 24


def audit(db, tenant_id: str, *, now: datetime | None = None) -> dict:
    """Read-only, tenant scoped, conservative readiness evaluation."""
    UUID(tenant_id)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("An aware UTC timestamp is required")
    migration = db.execute("""
        SELECT filename FROM ago_schema_migrations WHERE filename=%s
    """, (REQUIRED_MIGRATION,)).fetchone()
    tenant = db.execute("""
        SELECT id FROM ago_tenants WHERE id=%s
    """, (tenant_id,)).fetchone()
    if not tenant:
        raise ValueError("Requested company tenant not found")
    if migration is None:
        return {
            "tenant_id":tenant_id,"status":"degraded",
            "blockers":["missing_market_intelligence_migration"],
            "actions":["Back up the correct local database and apply reviewed SQL migrations."],
            "checked_at":now.isoformat(),
            "market_scan_age_seconds":None,
            "ready_for_autonomous_sales":False,
        }
    state = db.execute("""
        SELECT
          (SELECT COUNT(*) FROM ago_approval_requests a
             WHERE a.tenant_id=%s AND a.status='pending') AS approvals_pending,
          (SELECT COUNT(*) FROM ago_governed_tasks t
             WHERE t.tenant_id=%s AND t.status='failed') AS failed_tasks,
          (SELECT COUNT(*) FROM ago_governed_tasks t
             LEFT JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id AND q.task_id=t.id
             WHERE t.tenant_id=%s AND t.status='completed' AND q.id IS NULL)
             AS completed_awaiting_qa,
          (SELECT COUNT(*) FROM ago_governed_tasks t
             WHERE t.tenant_id=%s AND t.status='running'
               AND t.updated_at<%s::timestamptz-interval '24 hours')
             AS stalled_running_tasks,
          (SELECT COUNT(*) FROM ago_agent_runs r
             WHERE r.tenant_id=%s AND r.status='running'
               AND r.started_at<%s::timestamptz-interval '1 hour')
             AS stale_agent_runs,
          (SELECT COUNT(*) FROM ago_founder_intakes i
             JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
             WHERE i.tenant_id=%s AND p.status='draft') AS draft_projects,
          (SELECT COUNT(*) FROM ago_market_signals s
             WHERE s.tenant_id=%s) AS sourced_market_signals,
          (SELECT COUNT(*) FROM ago_marketing_drafts m
             WHERE m.tenant_id=%s AND m.stage='draft') AS unpublished_drafts
    """, (tenant_id, tenant_id,tenant_id,tenant_id,now,
           tenant_id,now,tenant_id,tenant_id,tenant_id)).fetchone()
    latest = db.execute("""
        SELECT MAX(checked_at) AS last_checked_at FROM ago_growth_scan_runs
        WHERE tenant_id=%s
    """, (tenant_id,)).fetchone()
    last = latest["last_checked_at"] if latest else None
    age = int(max(0, (now-last).total_seconds())) if last else None
    conditions = (
        ("market_worker_not_reporting",
         age is None or age>MAX_SCAN_AGE_SECONDS,
         "Start the local research worker and investigate the source-health ledger."),
        ("failed_governed_tasks",state["failed_tasks"]>0,
         "Inspect failed task evidence and obtain approval for a corrected plan."),
        ("completed_tasks_waiting_independent_qa",state["completed_awaiting_qa"]>0,
         "Request independent human QA before treating work as releasable."),
        ("stalled_task_leases",state["stalled_running_tasks"]>0,
         "Investigate task owner and reconcile stale work; do not replay external effects."),
        ("stale_agent_runs",state["stale_agent_runs"]>0,
         "Run the existing reviewed stale-agent reconciliation, not duplicate execution."),
    )
    blockers = [code for code,bad,_ in conditions if bad]
    actions = [action for _,bad,action in conditions if bad]
    result = {
        "tenant_id":tenant_id,
        "checked_at":now.isoformat(),
        "status":"degraded" if blockers else "observed_ok",
        "blockers":blockers,
        "operator_actions":actions,
        "market_scan_age_seconds":age,
        "observations":{key:int(value) for key,value in state.items()},
        "ready_for_autonomous_sales":False,
        "financial_evidence_present":False,
        "disclaimer":"Read-only health, not production certification; passing internal checks does not prove sales.",
    }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    args=parser.parse_args(argv)
    tenant_id=str(UUID(args.tenant_id))
    dsn=os.getenv("AGO_POSTGRES_DSN","")
    if (os.getenv("AGO_ENVIRONMENT","development") not in ("development","test","testing")
            or not local_database(dsn)):
        parser.error("Only configured localhost development/test database is permitted")
    try:
        with psycopg.connect(dsn,row_factory=dict_row,autocommit=True,connect_timeout=5) as db:
            result=audit(db,tenant_id)
    except (psycopg.Error,ValueError,KeyError,TypeError) as exc:
        result={
            "tenant_id":tenant_id,
            "status":"degraded",
            "blockers":["read_only_database_audit_failed"],
            "error_type":type(exc).__name__,
            "checked_at":datetime.now(timezone.utc).isoformat(),
            "ready_for_autonomous_sales":False,
        }
    print(json.dumps(result,sort_keys=True,default=str))
    return 0 if result["status"]=="observed_ok" else 2


if __name__=="__main__":
    raise SystemExit(main())
