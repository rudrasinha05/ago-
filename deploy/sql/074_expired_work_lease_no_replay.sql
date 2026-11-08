-- OOS durable queue: fail closed after any expired/unknown lease.
-- Never edit migration 036; install this additive, versioned hardening at 074.
-- IMPORTANT: this changes future lease eligibility but never deletes old events,
-- releases stuck queue entries, replays tasks, or modifies founder data by itself.
-- The original founder claimant can explicitly reconcile a timed-out lease,
-- which is terminal (not re-queued). No automatic retry after uncertain outcome.
CREATE OR REPLACE FUNCTION ago_oos_queue_lease_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous record; task_status text; agent_run_present boolean;
BEGIN
 SELECT e.state,e.sequence,e.expires_at INTO previous
 FROM ago_oos_queue_events e WHERE e.tenant_id=NEW.tenant_id AND e.queue_id=NEW.queue_id
 ORDER BY e.sequence DESC LIMIT 1;
 IF NEW.sequence<>coalesce(previous.sequence,0)+1 THEN
  RAISE EXCEPTION 'Out-of-order immutable work queue event'; END IF;
 IF NEW.state='leased' THEN
  -- A lease which timed out is still an unknown execution outcome.
  -- Its original side effects may have happened before a crash.
  -- Only a fresh queue item or a nonexpired, explicitly released lease
  -- may be leased; reconciliation is terminal and never automatic retry.
  IF previous.state IN ('reconciled','leased')
  THEN RAISE EXCEPTION 'Existing work lease cannot be stolen or replayed'; END IF;
  IF NEW.expires_at<=clock_timestamp() OR
     NEW.expires_at>clock_timestamp()+interval '1 hour' THEN
     RAISE EXCEPTION 'Work lease must be short-lived'; END IF;
  SELECT t.status INTO task_status FROM ago_oos_queue_items q
   JOIN ago_governed_tasks t ON t.tenant_id=q.tenant_id AND t.id=q.task_id
   WHERE q.tenant_id=NEW.tenant_id AND q.id=NEW.queue_id;
  IF task_status IS DISTINCT FROM 'waiting_approval' THEN
    RAISE EXCEPTION 'Only not-yet-running approved tasks may be leased'; END IF;
  SELECT EXISTS(
   SELECT 1 FROM ago_oos_queue_items q JOIN ago_agent_runs r
     ON r.tenant_id=q.tenant_id AND r.task_id=q.task_id
   WHERE q.tenant_id=NEW.tenant_id AND q.id=NEW.queue_id
  ) INTO agent_run_present;
  IF agent_run_present THEN
   RAISE EXCEPTION 'Previous agent attempt requires explicit operator reconciliation';
  END IF;
 ELSE
  IF previous.state IS DISTINCT FROM 'leased' THEN
    RAISE EXCEPTION 'Only active/expired leases may be released or reconciled'; END IF;
  IF NEW.state='released' AND previous.expires_at<=clock_timestamp() THEN
    RAISE EXCEPTION 'Expired lease needs operator reconciliation'; END IF;
 END IF;
 RETURN NEW;
END;
$$;
