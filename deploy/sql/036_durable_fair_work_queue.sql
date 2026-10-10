-- Section 21: persistent bounded allocation leases on existing governed tasks.
-- Leasing is NOT executing. Never automatically replay tool/model side effects.
CREATE TABLE ago_oos_queue_items (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 task_id uuid NOT NULL,
 operation_key text NOT NULL CHECK(length(trim(operation_key)) BETWEEN 1 AND 160),
 priority int NOT NULL CHECK(priority BETWEEN 0 AND 100),
 eligible_at timestamptz NOT NULL,
 enqueued_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,task_id),UNIQUE(tenant_id,operation_key),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,enqueued_by) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_oos_queue_fair ON ago_oos_queue_items
 (tenant_id,eligible_at,priority DESC,created_at,id);
CREATE TABLE ago_oos_queue_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 queue_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 state text NOT NULL CHECK(state IN ('leased','released','reconciled')),
 sequence bigint NOT NULL CHECK(sequence>0),
 expires_at timestamptz,
 explanation text NOT NULL CHECK(length(trim(explanation)) BETWEEN 1 AND 1000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,queue_id,sequence),
 FOREIGN KEY(tenant_id,queue_id) REFERENCES ago_oos_queue_items(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 CHECK((state='leased' AND expires_at IS NOT NULL)
    OR (state<>'leased' AND expires_at IS NULL))
);
CREATE INDEX ago_oos_queue_events_latest ON ago_oos_queue_events
 (tenant_id,queue_id,sequence DESC);
CREATE TRIGGER ago_queue_items_immutable BEFORE UPDATE OR DELETE ON ago_oos_queue_items
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_queue_events_immutable BEFORE UPDATE OR DELETE ON ago_oos_queue_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE FUNCTION ago_oos_queue_lease_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous record; task_status text; agent_run_present boolean;
BEGIN
 SELECT e.state,e.sequence,e.expires_at INTO previous
 FROM ago_oos_queue_events e WHERE e.tenant_id=NEW.tenant_id AND e.queue_id=NEW.queue_id
 ORDER BY e.sequence DESC LIMIT 1;
 IF NEW.sequence<>coalesce(previous.sequence,0)+1 THEN
  RAISE EXCEPTION 'Out-of-order immutable work queue event'; END IF;
 IF NEW.state='leased' THEN
  IF previous.state='reconciled'
   OR (previous.state='leased' AND previous.expires_at>clock_timestamp())
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
CREATE TRIGGER ago_oos_queue_transition BEFORE INSERT ON ago_oos_queue_events
 FOR EACH ROW EXECUTE FUNCTION ago_oos_queue_lease_guard();
