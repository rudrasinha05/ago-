"""Offline invariant checks for local operations acceptance pulse."""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest

ROOT=Path(__file__).resolve().parents[3]
spec=spec_from_file_location("company_readiness_audit",ROOT/"scripts/company_readiness_audit.py")
pulse=module_from_spec(spec)
spec.loader.exec_module(pulse)


class Row:
    def __init__(self, data):
        self.data=data
    def fetchone(self):
        return self.data


class ReadOnlyDB:
    def __init__(self, last_scan, metrics=None, migration=True, tenant=True):
        self.last_scan=last_scan
        self.metrics=metrics or {
            "approvals_pending":0,"failed_tasks":0,"completed_awaiting_qa":0,
            "stalled_running_tasks":0,"stale_agent_runs":0,"draft_projects":0,
            "sourced_market_signals":3,"unpublished_drafts":1,
        }
        self.migration=migration
        self.tenant=tenant
        self.queries=[]
    def execute(self, sql, params):
        self.queries.append((sql,params))
        if "FROM ago_schema_migrations" in sql:
            return Row({"filename":pulse.REQUIRED_MIGRATION} if self.migration else None)
        if "FROM ago_tenants" in sql:
            return Row({"id":params[0]} if self.tenant else None)
        if "AS approvals_pending" in sql:
            return Row(self.metrics)
        if "MAX(checked_at)" in sql:
            return Row({"last_checked_at":self.last_scan})
        raise AssertionError("Unexpected SQL in read-only audit")


def test_report_is_derived_from_stored_scans_and_qa_not_fiction():
    company=str(uuid4())
    now=datetime(2026,10,21,12,0,tzinfo=timezone.utc)
    db=ReadOnlyDB(now-timedelta(minutes=20))
    result=pulse.audit(db,company,now=now)
    assert result["status"]=="observed_ok"
    assert result["market_scan_age_seconds"]==1200
    assert result["ready_for_autonomous_sales"] is False
    assert result["financial_evidence_present"] is False
    assert result["observations"]["sourced_market_signals"]==3
    assert all("INSERT " not in query and "UPDATE " not in query
               for query,_ in db.queries)
    assert all(params[0]==company for query,params in db.queries
               if "ago_schema_migrations" not in query)


def test_audit_detects_missed_research_cycles_and_qa_remediation():
    company=str(uuid4())
    now=datetime(2026,10,21,12,0,tzinfo=timezone.utc)
    db=ReadOnlyDB(now-timedelta(hours=4),metrics={
        "approvals_pending":2,"failed_tasks":1,"completed_awaiting_qa":2,
        "stalled_running_tasks":1,"stale_agent_runs":1,"draft_projects":1,
        "sourced_market_signals":0,"unpublished_drafts":0,
    })
    result=pulse.audit(db,company,now=now)
    assert result["status"]=="degraded"
    assert set(result["blockers"])=={
        "market_worker_not_reporting","failed_governed_tasks",
        "completed_tasks_waiting_independent_qa","stalled_task_leases",
        "stale_agent_runs",
    }
    assert result["operator_actions"]
    assert not result["ready_for_autonomous_sales"]


def test_audit_rejects_invalid_tenant_and_missing_schema():
    now=datetime(2026,10,21,12,0,tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        pulse.audit(ReadOnlyDB(now),"not-a-tenant",now=now)
    with pytest.raises(ValueError):
        pulse.audit(ReadOnlyDB(now,tenant=False),str(uuid4()),now=now)
    result=pulse.audit(ReadOnlyDB(now,migration=False),str(uuid4()),now=now)
    assert result["blockers"]==["missing_market_intelligence_migration"]
    assert result["status"]=="degraded"
