-- Sections 26-27: independently reviewed evolution evidence and descriptive
-- follow-up comparisons. No autonomous source change or "calibrated" forecast.
CREATE TABLE ago_evolution_review_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 observation_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 decision text NOT NULL CHECK(decision IN ('endorsed','rejected')),
 rollback_plan text NOT NULL CHECK(length(trim(rollback_plan)) BETWEEN 1 AND 3000),
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,observation_id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,observation_id) REFERENCES ago_evolution_observations(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE FUNCTION ago_evolution_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.action<>'enterprise:evolution:review:'||NEW.observation_id::text
 OR a.status<>'approved' OR a.requester_id<>NEW.actor_id
 OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id THEN
   RAISE EXCEPTION 'Independent evolution review required';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_evolution_review_authorized BEFORE INSERT ON ago_evolution_review_events
 FOR EACH ROW EXECUTE FUNCTION ago_evolution_review_guard();
CREATE TRIGGER ago_evolution_review_immutable BEFORE UPDATE OR DELETE ON ago_evolution_review_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE TABLE ago_twin_observed_comparisons (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 scenario_id uuid NOT NULL,
 later_snapshot_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 outcome jsonb NOT NULL CHECK(jsonb_typeof(outcome)='object'
   AND outcome->>'calibration'='descriptive_only'
   AND outcome->>'applied'='false'),
 rationale text NOT NULL CHECK(length(trim(rationale)) BETWEEN 1 AND 2000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,scenario_id,later_snapshot_id),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,scenario_id) REFERENCES ago_twin_scenarios(tenant_id,id),
 FOREIGN KEY(tenant_id,later_snapshot_id) REFERENCES ago_executive_snapshots(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE FUNCTION ago_twin_comparison_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approval record; original record; later record;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO approval FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR approval.action<>('enterprise:twin:compare:'||
   NEW.scenario_id::text||':'||NEW.later_snapshot_id::text)
 OR approval.status<>'approved' OR approval.requester_id<>NEW.actor_id
 OR approval.reviewer_id IS NULL OR approval.reviewer_id=approval.requester_id THEN
  RAISE EXCEPTION 'Independent twin outcome review required';
 END IF;
 SELECT t.created_at AS created_at,s.created_at AS base_at INTO original
 FROM ago_twin_scenarios t JOIN ago_executive_snapshots s
 ON s.tenant_id=t.tenant_id AND s.id=t.snapshot_id
 WHERE t.tenant_id=NEW.tenant_id AND t.id=NEW.scenario_id;
 SELECT created_at INTO later FROM ago_executive_snapshots
 WHERE tenant_id=NEW.tenant_id AND id=NEW.later_snapshot_id;
 IF original.created_at IS NULL OR later.created_at IS NULL
 OR later.created_at<=original.created_at THEN
  RAISE EXCEPTION 'Observed snapshot must be later than simulated scenario';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_twin_comparison_verified BEFORE INSERT ON ago_twin_observed_comparisons
 FOR EACH ROW EXECUTE FUNCTION ago_twin_comparison_guard();
CREATE TRIGGER ago_twin_comparison_immutable BEFORE UPDATE OR DELETE ON ago_twin_observed_comparisons
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
