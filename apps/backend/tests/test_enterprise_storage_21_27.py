"""Sections 21–27 actual PostgreSQL safety and migration-024 negative tests.

All fixtures use an isolated CI database and rollback; do not point these tests
at the founder's real personal organization.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from test_m7_http_postgres import case as case
from ago.governance import ApprovalRepository
from ago.organization_store import OrganizationStore
from ago.executive_intelligence import ExecutiveIntelligence


def ids(info):
    return info["tenant"], info["founder_id"], info["reviewer_id"]


def approve(info, action):
    tenant, founder, reviewer = ids(info)
    store = ApprovalRepository(info["db"])
    request = store.propose(tenant_id=tenant, action=action, requester_id=founder)
    return request.request_id, lambda: store.decide(
        request_id=request.request_id, tenant_id=tenant,
        reviewer_id=reviewer, approve=True,
        reason="Independent case review", authorized=True)


def test_oos_mode_history_requires_exact_real_human_approval_and_is_immutable(case):
    _, _, info = case
    db = info["db"]
    tenant, founder, _ = ids(info)
    permission, decision = approve(info, "enterprise:mode:company:company:paused")
    event_id = str(uuid4())
    sql = """INSERT INTO ago_oos_mode_events
        (id,tenant_id,scope_kind,scope_id,mode,sequence,actor_id,approval_id,rationale)
        VALUES (%s,%s,'company',NULL,'paused',1,%s,%s,'Operator reviewed')"""
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(sql, (event_id, tenant, founder, permission))
    decision()
    db.execute(sql, (event_id, tenant, founder, permission))
    assert db.execute("SELECT mode FROM ago_oos_mode_events WHERE id=%s",
                      (event_id,)).fetchone()["mode"] == "paused"
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("DELETE FROM ago_oos_mode_events WHERE id=%s", (event_id,))
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, founder, permission))


def test_agent_state_snapshot_scoped_to_real_employee_and_append_only(case):
    _, _, info = case
    db = info["db"]
    tenant, _, _ = ids(info)
    org = OrganizationStore(db)
    dept = org.add_department(tenant_id=tenant, name="Operations")
    agent = org.hire(tenant_id=tenant, department_id=dept.id,
                     name="State Agent", kind="ai")
    sql = """INSERT INTO ago_agent_state_snapshots
      (id,tenant_id,employee_id,available_units,active_count,queued_count,
       availability,state,evidence_digest,source_ref)
       VALUES (%s,%s,%s,10,2,1,'available','{}'::jsonb,%s,'real:tasks')"""
    identifier = str(uuid4())
    db.execute(sql, (identifier, tenant, agent.id, "b" * 64))
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, str(uuid4()), "b" * 64))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("UPDATE ago_agent_state_snapshots SET active_count=5 WHERE id=%s",
                   (identifier,))


def test_horizon_parent_tenancy_and_window_checks(case):
    _, _, info = case
    db = info["db"]
    tenant, founder, _ = ids(info)
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    parent = str(uuid4())
    sql = """INSERT INTO ago_horizon_plans
        (id,tenant_id,parent_id,owner_id,horizon,title,starts_at,ends_at,evidence_ref)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'reviewed:vision')"""
    db.execute(sql, (parent, tenant, None, founder, "lifetime", "Company Vision",
                     now, now + timedelta(days=3650)))
    child = str(uuid4())
    db.execute(sql, (child, tenant, parent, founder, "five_year", "Five-Year Plan",
                     now, now + timedelta(days=1825)))
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, str(uuid4()), founder,
                         "annual", "Unknown Parent", now, now + timedelta(days=365)))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("DELETE FROM ago_horizon_plans WHERE id=%s", (child,))


def test_cost_evidence_cannot_be_self_certified(case):
    _, _, info = case
    db = info["db"]
    tenant, founder, _ = ids(info)
    sql = """INSERT INTO ago_observed_costs
       (id,tenant_id,operation_key,category,provider,source_ref,observed_amount,
        currency,period_start,period_end,evidence_state,recorded_by)
       VALUES (%s,%s,%s,'model','test-provider','unverified:invoice',12.5,
         'INR',now()-interval '1 day',now(),%s,%s)"""
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, "cost-1", "verified", founder))
    good_id = str(uuid4())
    db.execute(sql, (good_id, tenant, "cost-1", "unverified", founder))
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, "cost-1", "unverified", founder))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("UPDATE ago_observed_costs SET observed_amount=500 WHERE id=%s",
                   (good_id,))


def test_approved_budget_only_and_no_history_rewrites(case):
    _, _, info = case
    db = info["db"]
    tenant, _, _ = ids(info)
    budget_id = str(uuid4())
    approval_id, decide = approve(info, "enterprise:budget:" + budget_id)
    sql = """INSERT INTO ago_budget_envelopes
       (id,tenant_id,scope_kind,scope_id,approved_ceiling,currency,approval_id)
       VALUES (%s,%s,'company',NULL,100,'INR',%s)"""
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(sql, (budget_id, tenant, approval_id))
    decide()
    db.execute(sql, (budget_id, tenant, approval_id))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("UPDATE ago_budget_envelopes SET approved_ceiling=1000 WHERE id=%s",
                   (budget_id,))


def test_marketplace_publish_and_use_require_separate_reviews(case):
    _, _, info = case
    db = info["db"]
    tenant, founder, _ = ids(info)
    dept = OrganizationStore(db).add_department(tenant_id=tenant, name="Shared Library")
    asset = str(uuid4())
    db.execute("""INSERT INTO ago_marketplace_assets
      (id,tenant_id,owner_department_id,publisher_id,name,asset_kind,
       version,digest,license_id,manifest)
       VALUES(%s,%s,%s,%s,'Shared Patterns','library','1.0.0',%s,'MIT','{}'::jsonb)""",
       (asset, tenant, dept.id, founder, "c" * 64))
    pub, review = approve(info, "enterprise:publish:" + asset)
    db.execute("UPDATE ago_marketplace_assets SET status='proposed',approval_id=%s WHERE id=%s",
               (pub, asset))
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("UPDATE ago_marketplace_assets SET status='published' WHERE id=%s", (asset,))
    review()
    db.execute("UPDATE ago_marketplace_assets SET status='published' WHERE id=%s", (asset,))
    use, use_review = approve(info, "enterprise:consume:" + asset)
    sql = """INSERT INTO ago_asset_consumptions
      (id,tenant_id,asset_id,consumer_department_id,actor_id,approval_id,evidence_ref)
      VALUES (%s,%s,%s,%s,%s,%s,'reviewed:reusable-license')"""
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, asset, dept.id, founder, use))
    use_review()
    db.execute(sql, (str(uuid4()), tenant, asset, dept.id, founder, use))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("UPDATE ago_marketplace_assets SET digest=%s WHERE id=%s", ("d" * 64, asset))


def test_evolution_evidence_cannot_self_review(case):
    _, _, info = case
    db = info["db"]
    tenant, _, _ = ids(info)
    sql = """INSERT INTO ago_evolution_observations
       (id,tenant_id,baseline_digest,candidate_digest,metrics,source_ref,review_state)
       VALUES (%s,%s,%s,%s,'{}'::jsonb,'verified:qa-log',%s)"""
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, "a" * 64, "b" * 64, "reviewed"))
    observation_id = str(uuid4())
    db.execute(sql, (observation_id, tenant, "a" * 64, "b" * 64, "unreviewed"))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("DELETE FROM ago_evolution_observations WHERE id=%s", (observation_id,))


def test_digital_twin_is_hypothetical_uncalibrated_and_append_only(case):
    client, headers, info = case
    db = info["db"]
    tenant, founder, _ = ids(info)
    snapshot = ExecutiveIntelligence(db).capture(tenant_id=tenant, analyst_id=founder)
    sql = """INSERT INTO ago_twin_scenarios
      (id,tenant_id,snapshot_id,actor_id,assumptions,result,data_coverage,
       calibrated,source_digest)
      VALUES (%s,%s,%s,%s,'{}'::jsonb,'{"read_only":true}'::jsonb,'partial',%s,%s)"""
    psycopg = pytest.importorskip("psycopg")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(sql, (str(uuid4()), tenant, snapshot["id"], founder, True,
                         snapshot["digest"]))
    twin_id = str(uuid4())
    db.execute(sql, (twin_id, tenant, snapshot["id"], founder, False,
                     snapshot["digest"]))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute("UPDATE ago_twin_scenarios SET calibrated=true WHERE id=%s", (twin_id,))
    assert client.get("/v1/meta/snapshots/" + snapshot["id"],
                      headers=headers["founder"]).status_code == 200
