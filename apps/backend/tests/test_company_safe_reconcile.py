"""Founder-controlled local recovery never replays jobs or bypasses approval."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest

SCRIPT=Path(__file__).resolve().parents[3]/"scripts"/"company_safe_reconcile.py"
SPEC=spec_from_file_location("ago_safe_reconcile",SCRIPT)
recovery=module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class Db:
    def execute(self, query, params):
        assert "COUNT(*)" in query and "status='running'" in query
        return self
    def fetchone(self):
        return {"total":102}


def test_local_only_and_explicit_founder_control():
    tenant=str(uuid4())
    dsn="postgresql://ago:private@localhost:5432/ago_dev"
    assert recovery.validate_local(dsn,"development",tenant,3600,
           apply=False,confirm=None)==tenant
    with pytest.raises(PermissionError):
        recovery.validate_local(dsn,"development",tenant,3600,
            apply=True,confirm=None)
    with pytest.raises(PermissionError):
        recovery.validate_local(dsn,"production",tenant,3600,
            apply=True,confirm=recovery.CONFIRM)
    with pytest.raises(PermissionError):
        recovery.validate_local("postgresql://ago:secret@remote.example/ago",
            "development",tenant,3600,apply=True,confirm=recovery.CONFIRM)
    with pytest.raises(ValueError):
        recovery.validate_local(dsn,"test",tenant,30,apply=False,confirm=None)


def test_dry_run_cannot_mark_failed_or_replay():
    result=recovery.reconcile(Db(),str(uuid4()),3600,apply=False)
    assert result["observed_stale_runs"]==102
    assert result["marked_failed"]==0
    assert result["external_actions_replayed"] is False
    assert result["mode"]=="read_only"


def test_apply_uses_preexisting_bounded_reconcile_without_external_dispatch(monkeypatch):
    import ago.agent_runtime
    batches=[100,2]
    calls=[]
    class FakeRuntime:
        def __init__(self,db):
            assert isinstance(db,Db)
        def recover_stale(self,*,tenant_id,minimum_age_seconds):
            calls.append((tenant_id,minimum_age_seconds))
            return batches.pop(0)
    monkeypatch.setattr(ago.agent_runtime,"AgentRuntime",FakeRuntime)
    tenant=str(uuid4())
    result=recovery.reconcile(Db(),tenant,3600,apply=True)
    assert result["marked_failed"]==102
    assert result["external_actions_replayed"] is False
    assert calls==[(tenant,3600)]*2
