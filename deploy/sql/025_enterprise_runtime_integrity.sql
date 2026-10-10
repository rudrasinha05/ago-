-- AGO Sections 21-27: additive governance enforcement on actual task dispatch.
-- Previously applied migrations 001-024 are never edited or re-applied.
-- This migration changes only tenant-bound operational controls on disposable CI.
CREATE TABLE ago_worker_state_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 employee_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 state text NOT NULL CHECK (state IN ('available','idle','paused','sleeping',
                                     'interrupted','unavailable','terminated')),
 sequence bigint NOT NULL CHECK (sequence>0),
 reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 3000),
 expires_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,employee_id,sequence),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE INDEX ago_worker_state_current
 ON ago_worker_state_events(tenant_id,employee_id,sequence DESC);

CREATE FUNCTION ago_guard_worker_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_state text; last_sequence bigint; a record; valid boolean := false;
BEGIN
 IF TG_OP<>'INSERT' THEN
   RAISE EXCEPTION 'Employee state history is immutable';
 END IF;
 SELECT action,status,requester_id,reviewer_id INTO a
 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.action <> 'enterprise:worker:'||NEW.employee_id::text||':'||NEW.state
    OR a.status<>'approved' OR a.requester_id<>NEW.actor_id
    OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id THEN
    RAISE EXCEPTION 'Human independent worker-state approval required';
 END IF;
 SELECT state,sequence INTO old_state,last_sequence FROM ago_worker_state_events
 WHERE tenant_id=NEW.tenant_id AND employee_id=NEW.employee_id
 ORDER BY sequence DESC LIMIT 1;
 old_state := coalesce(old_state,'available');
 IF NEW.sequence <> coalesce(last_sequence,0)+1 THEN
   RAISE EXCEPTION 'Worker sequence conflict';
 END IF;
 valid := CASE old_state
  WHEN 'available' THEN NEW.state IN ('idle','paused','interrupted','unavailable')
  WHEN 'idle' THEN NEW.state IN ('available','paused','sleeping','unavailable')
  WHEN 'paused' THEN NEW.state IN ('available','idle','sleeping','unavailable')
  WHEN 'sleeping' THEN NEW.state IN ('idle','unavailable')
  WHEN 'interrupted' THEN NEW.state IN ('paused','unavailable')
  WHEN 'unavailable' THEN NEW.state IN ('idle','terminated')
  ELSE false END;
 IF NOT valid THEN RAISE EXCEPTION 'Illegal worker-state transition'; END IF;
 IF NEW.state IN ('paused','sleeping','interrupted') AND
    (NEW.expires_at IS NULL OR NEW.expires_at<=clock_timestamp()
       OR NEW.expires_at>clock_timestamp()+interval '7 days') THEN
   RAISE EXCEPTION 'Temporary worker restriction must be bounded';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_worker_states_guard BEFORE INSERT OR UPDATE OR DELETE ON ago_worker_state_events
 FOR EACH ROW EXECUTE FUNCTION ago_guard_worker_state();

-- Every task/agent launch must enforce company, department and employee modes,
-- not merely trust a best-effort frontend/preview, including after process restart.
CREATE FUNCTION ago_dispatch_mode_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE tenant uuid; employee uuid; department uuid; current_mode text;
        last_mode record; last_worker record;
BEGIN
 IF TG_TABLE_NAME='ago_governed_tasks' THEN
  IF NOT (NEW.status='running' AND
      (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status)) THEN
    RETURN NEW;
  END IF;
  tenant:=NEW.tenant_id; employee:=NEW.assignee_id;
 ELSE
  IF NEW.status<>'running' THEN RETURN NEW; END IF;
  tenant:=NEW.tenant_id; employee:=NEW.agent_id;
 END IF;
 SELECT department_id INTO department FROM ago_employees
 WHERE tenant_id=tenant AND id=employee;
 IF department IS NULL THEN RAISE EXCEPTION 'Missing tenant worker identity'; END IF;
 SELECT mode,expires_at INTO last_mode FROM ago_oos_mode_events
 WHERE tenant_id=tenant AND scope_kind='company' AND scope_id IS NULL
 ORDER BY sequence DESC LIMIT 1;
 IF FOUND AND (last_mode.mode<>'active' OR last_mode.expires_at<=clock_timestamp()) THEN
   RAISE EXCEPTION 'Organization operating mode blocks execution';
 END IF;
 SELECT mode,expires_at INTO last_mode FROM ago_oos_mode_events
 WHERE tenant_id=tenant AND scope_kind='department' AND scope_id=department
 ORDER BY sequence DESC LIMIT 1;
 IF FOUND AND (last_mode.mode<>'active' OR last_mode.expires_at<=clock_timestamp()) THEN
   RAISE EXCEPTION 'Department operating mode blocks execution';
 END IF;
 SELECT mode,expires_at INTO last_mode FROM ago_oos_mode_events
 WHERE tenant_id=tenant AND scope_kind='employee' AND scope_id=employee
 ORDER BY sequence DESC LIMIT 1;
 IF FOUND AND (last_mode.mode<>'active' OR last_mode.expires_at<=clock_timestamp()) THEN
   RAISE EXCEPTION 'Worker operating mode blocks execution';
 END IF;
 SELECT state,expires_at INTO last_worker FROM ago_worker_state_events
 WHERE tenant_id=tenant AND employee_id=employee ORDER BY sequence DESC LIMIT 1;
 IF FOUND AND (last_worker.state NOT IN ('available','idle') OR
   (last_worker.expires_at IS NOT NULL AND last_worker.expires_at<=clock_timestamp())) THEN
   RAISE EXCEPTION 'Worker state blocks execution';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_task_execution_oos BEFORE INSERT OR UPDATE ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_dispatch_mode_guard();
CREATE TRIGGER ago_agent_run_execution_oos BEFORE INSERT ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_dispatch_mode_guard();

-- Financial and marketplace events are never treated as external settlement.
-- Catalog lifecycle changes after publication require a separate reviewed event.
CREATE TABLE ago_marketplace_lifecycle_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 asset_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 target_state text NOT NULL CHECK(target_state IN ('deprecated','revoked')),
 reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 3000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES ago_marketplace_assets(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE FUNCTION ago_marketplace_lifecycle_event_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE decision record;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Marketplace lifecycle history immutable'; END IF;
 SELECT action,status,requester_id,reviewer_id INTO decision FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR decision.action <> 'enterprise:asset:'||NEW.asset_id::text||':'||NEW.target_state
 OR decision.status<>'approved' OR decision.requester_id<>NEW.actor_id
 OR decision.reviewer_id IS NULL OR decision.reviewer_id=decision.requester_id THEN
   RAISE EXCEPTION 'Independent exact asset lifecycle approval required';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_asset_lifecycle_immutable
 BEFORE INSERT OR UPDATE OR DELETE ON ago_marketplace_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION ago_marketplace_lifecycle_event_guard();
CREATE FUNCTION ago_marketplace_status_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND OLD.status IS DISTINCT FROM NEW.status AND
    NEW.status IN ('deprecated','revoked') AND
    NOT EXISTS (SELECT 1 FROM ago_marketplace_lifecycle_events e
                WHERE e.tenant_id=NEW.tenant_id AND e.asset_id=NEW.id
                  AND e.target_state=NEW.status
                  AND e.approval_id=NEW.approval_id) THEN
    RAISE EXCEPTION 'Asset sunset requires exact independently reviewed lifecycle event';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_marketplace_retirement_requires_review
 BEFORE UPDATE ON ago_marketplace_assets
 FOR EACH ROW EXECUTE FUNCTION ago_marketplace_status_approval();

CREATE FUNCTION ago_marketplace_published_use() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM ago_marketplace_assets
    WHERE tenant_id=NEW.tenant_id AND id=NEW.asset_id AND status='published') THEN
   RAISE EXCEPTION 'Cross-tenant or unpublished asset cannot be consumed';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_marketplace_use_active_guard
 BEFORE INSERT ON ago_asset_consumptions
 FOR EACH ROW EXECUTE FUNCTION ago_marketplace_published_use();

-- Prevent simulation row forgery / mismatched production snapshot digests.
CREATE FUNCTION ago_twin_provenance_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.result->>'read_only') IS DISTINCT FROM 'true'
    OR (NEW.result ? 'applied' AND (NEW.result->>'applied') IS DISTINCT FROM 'false') OR NEW.calibrated THEN
   RAISE EXCEPTION 'Simulated data cannot authorize or claim production mutations';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM ago_executive_snapshots
    WHERE tenant_id=NEW.tenant_id AND id=NEW.snapshot_id AND digest=NEW.source_digest) THEN
   RAISE EXCEPTION 'Twin source digest/tenant cannot be forged';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_twin_evidence_integrity BEFORE INSERT ON ago_twin_scenarios
 FOR EACH ROW EXECUTE FUNCTION ago_twin_provenance_guard();
