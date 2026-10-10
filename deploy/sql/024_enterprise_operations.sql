-- AGO Sections 21-27: additive, tenant-bound enterprise operating records.
-- Development-only migration: operator must back up live local DB before applying.
-- No automatic organizational decisions, financial settlement or LLM execution.

CREATE TABLE ago_oos_mode_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 scope_kind text NOT NULL CHECK (scope_kind IN ('company','department','employee')),
 scope_id uuid,
 mode text NOT NULL CHECK (mode IN ('active','paused','maintenance','emergency','suspended')),
 sequence bigint NOT NULL CHECK (sequence > 0),
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 rationale text NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 3000),
 expires_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,scope_kind,scope_id,sequence),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((scope_kind='company' AND scope_id IS NULL)
    OR (scope_kind<>'company' AND scope_id IS NOT NULL))
);
-- company-level rows use partial unique index because SQL NULL != NULL.
CREATE UNIQUE INDEX ago_oos_company_sequence
 ON ago_oos_mode_events(tenant_id,sequence) WHERE scope_kind='company';
CREATE INDEX ago_oos_mode_history ON ago_oos_mode_events(tenant_id,created_at DESC,id);

CREATE TABLE ago_agent_state_snapshots (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 employee_id uuid NOT NULL,
 observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 available_units int NOT NULL CHECK(available_units BETWEEN 0 AND 100000),
 active_count int NOT NULL CHECK(active_count BETWEEN 0 AND 100000),
 queued_count int NOT NULL CHECK(queued_count BETWEEN 0 AND 100000),
 availability text NOT NULL CHECK(availability IN
  ('available','idle','paused','sleeping','interrupted','unavailable','terminated','unknown')),
 state jsonb NOT NULL CHECK(jsonb_typeof(state)='object'),
 evidence_digest text NOT NULL CHECK(evidence_digest ~ '^[0-9a-f]{64}$'),
 source_ref text NOT NULL CHECK(length(trim(source_ref)) BETWEEN 1 AND 1024),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id)
);
CREATE INDEX ago_agent_state_history
 ON ago_agent_state_snapshots(tenant_id,employee_id,observed_at DESC,id);

CREATE TABLE ago_horizon_plans (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 parent_id uuid,
 goal_id uuid,
 owner_id uuid NOT NULL,
 horizon text NOT NULL CHECK(horizon IN
  ('lifetime','five_year','annual','quarterly','monthly','weekly','daily','hourly','current_task')),
 title text NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 300),
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL,
 budget_ceiling numeric(20,6) NOT NULL DEFAULT 0 CHECK(budget_ceiling >= 0),
 revision int NOT NULL DEFAULT 1 CHECK(revision > 0),
 approval_id uuid,
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,parent_id) REFERENCES ago_horizon_plans(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK(starts_at < ends_at), CHECK(id IS DISTINCT FROM parent_id)
);
CREATE INDEX ago_horizon_parent ON ago_horizon_plans(tenant_id,parent_id,horizon);

CREATE TABLE ago_observed_costs (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 operation_key text NOT NULL CHECK(length(trim(operation_key)) BETWEEN 1 AND 200),
 category text NOT NULL CHECK(category IN ('model','storage','tool','execution','time','revenue','other')),
 provider text NOT NULL CHECK(length(trim(provider)) BETWEEN 1 AND 180),
 source_ref text NOT NULL CHECK(length(trim(source_ref)) BETWEEN 1 AND 1024),
 observed_amount numeric(20,6) NOT NULL CHECK(observed_amount >= 0),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 period_start timestamptz NOT NULL, period_end timestamptz NOT NULL,
 evidence_state text NOT NULL DEFAULT 'unverified'
   CHECK(evidence_state IN ('unverified','verified','rejected')),
 recorded_by uuid NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,provider,operation_key),
 FOREIGN KEY(tenant_id,recorded_by) REFERENCES ago_users(tenant_id,id),
 CHECK(period_start < period_end)
);
CREATE INDEX ago_costs_tenant_period ON ago_observed_costs(tenant_id,period_start DESC,id);

CREATE TABLE ago_budget_envelopes (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 scope_kind text NOT NULL CHECK(scope_kind IN ('company','department','employee')),
 scope_id uuid,
 approved_ceiling numeric(20,6) NOT NULL CHECK(approved_ceiling >= 0),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK((scope_kind='company' AND scope_id IS NULL)
    OR (scope_kind<>'company' AND scope_id IS NOT NULL))
);
CREATE INDEX ago_budget_scope ON ago_budget_envelopes(tenant_id,scope_kind,scope_id);

CREATE TABLE ago_marketplace_assets (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 owner_department_id uuid NOT NULL,
 publisher_id uuid NOT NULL,
 name text NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 200),
 asset_kind text NOT NULL CHECK(asset_kind IN
  ('service','library','dataset','research','design_system','template','agent','model','workflow')),
 version text NOT NULL CHECK(version ~ '^[0-9]+[.][0-9]+[.][0-9]+$'),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 license_id text NOT NULL CHECK(length(trim(license_id)) BETWEEN 1 AND 200),
 manifest jsonb NOT NULL CHECK(jsonb_typeof(manifest)='object'),
 status text NOT NULL DEFAULT 'draft' CHECK(status IN
  ('draft','proposed','published','deprecated','revoked')),
 approval_id uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,owner_department_id,name,version),
 FOREIGN KEY(tenant_id,owner_department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY(tenant_id,publisher_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE TABLE ago_asset_consumptions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 asset_id uuid NOT NULL,
 consumer_department_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES ago_marketplace_assets(tenant_id,id),
 FOREIGN KEY(tenant_id,consumer_department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE INDEX ago_assets_discovery ON ago_marketplace_assets(tenant_id,status,asset_kind);

CREATE TABLE ago_evolution_observations (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 recommendation_id uuid,
 baseline_digest text NOT NULL CHECK(baseline_digest ~ '^[a-f0-9]{64}$'),
 candidate_digest text NOT NULL CHECK(candidate_digest ~ '^[a-f0-9]{64}$'),
 metrics jsonb NOT NULL CHECK(jsonb_typeof(metrics)='object'),
 source_ref text NOT NULL CHECK(length(trim(source_ref)) BETWEEN 1 AND 1024),
 review_state text NOT NULL DEFAULT 'unreviewed'
   CHECK(review_state IN ('unreviewed','reviewed','rejected')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,recommendation_id) REFERENCES ago_meta_recommendations(tenant_id,id),
 CHECK(baseline_digest<>candidate_digest)
);
CREATE TABLE ago_twin_scenarios (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 snapshot_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 assumptions jsonb NOT NULL CHECK(jsonb_typeof(assumptions)='object'),
 result jsonb NOT NULL CHECK(jsonb_typeof(result)='object'),
 data_coverage text NOT NULL CHECK(data_coverage IN ('unknown','partial','verified')),
 calibrated boolean NOT NULL DEFAULT false,
 source_digest text NOT NULL CHECK(source_digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,snapshot_id) REFERENCES ago_executive_snapshots(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);

-- Evidence/history append-only irrespective of buggy application callers.
CREATE FUNCTION ago_enterprise_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Enterprise evidence is append-only';
END;
$$;
CREATE TRIGGER ago_oos_events_immutable BEFORE UPDATE OR DELETE ON ago_oos_mode_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_agent_states_immutable BEFORE UPDATE OR DELETE ON ago_agent_state_snapshots
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_planning_immutable BEFORE UPDATE OR DELETE ON ago_horizon_plans
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_costs_immutable BEFORE UPDATE OR DELETE ON ago_observed_costs
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_budget_history_immutable BEFORE UPDATE OR DELETE ON ago_budget_envelopes
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_asset_consumptions_immutable BEFORE UPDATE OR DELETE ON ago_asset_consumptions
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_evolution_history_immutable BEFORE UPDATE OR DELETE ON ago_evolution_observations
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_twin_scenarios_immutable BEFORE UPDATE OR DELETE ON ago_twin_scenarios
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

-- Additional fail-closed controls for privileged and evidence-bearing writes.
-- No privileged enterprise row is authorized merely because AI supplied an approval id.
ALTER TABLE ago_oos_mode_events ADD CONSTRAINT ago_oos_unique_approval UNIQUE(tenant_id,approval_id);
ALTER TABLE ago_budget_envelopes ADD CONSTRAINT ago_budget_unique_approval UNIQUE(tenant_id,approval_id);
ALTER TABLE ago_asset_consumptions ADD CONSTRAINT ago_consumption_unique_approval UNIQUE(tenant_id,approval_id);

CREATE FUNCTION ago_enterprise_write_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected text; a record;
BEGIN
 IF TG_TABLE_NAME='ago_observed_costs' AND NEW.evidence_state<>'unverified' THEN
   RAISE EXCEPTION 'Cost evidence requires external verification';
 END IF;
 IF TG_TABLE_NAME='ago_evolution_observations' AND NEW.review_state<>'unreviewed' THEN
   RAISE EXCEPTION 'Evolution observations are not self-reviewed';
 END IF;
 IF TG_TABLE_NAME='ago_twin_scenarios' AND NEW.calibrated THEN
   RAISE EXCEPTION 'Twin calibration requires independently measured outcomes';
 END IF;
 IF TG_TABLE_NAME='ago_marketplace_assets' THEN
   IF TG_OP='INSERT' AND (NEW.status<>'draft' OR NEW.approval_id IS NOT NULL) THEN
     RAISE EXCEPTION 'Marketplace assets start as unpublished drafts';
   END IF;
   IF TG_OP='UPDATE' THEN
     IF (to_jsonb(OLD)-'status'-'approval_id') IS DISTINCT FROM
        (to_jsonb(NEW)-'status'-'approval_id') THEN
       RAISE EXCEPTION 'Published asset metadata and ownership are immutable';
     END IF;
     IF NOT ((OLD.status='draft' AND NEW.status='proposed')
           OR (OLD.status='proposed' AND NEW.status='published')
           OR (OLD.status='published' AND NEW.status IN ('deprecated','revoked'))
           OR (OLD.status='deprecated' AND NEW.status='revoked')) THEN
       RAISE EXCEPTION 'Illegal asset lifecycle transition';
     END IF;
   END IF;
   IF NEW.status='published' THEN
     expected := 'enterprise:publish:'||NEW.id::text;
   ELSE
     RETURN NEW;
   END IF;
 ELSIF TG_TABLE_NAME='ago_oos_mode_events' THEN
   expected := 'enterprise:mode:'||NEW.scope_kind||':'||
               coalesce(NEW.scope_id::text,'company')||':'||NEW.mode;
 ELSIF TG_TABLE_NAME='ago_budget_envelopes' THEN
   expected := 'enterprise:budget:'||NEW.id::text;
 ELSIF TG_TABLE_NAME='ago_asset_consumptions' THEN
   expected := 'enterprise:consume:'||NEW.asset_id::text;
 ELSE
   RETURN NEW;
 END IF;
 SELECT action,status,requester_id,reviewer_id INTO a
 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.action<>expected OR a.status<>'approved'
      OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id THEN
   RAISE EXCEPTION 'Exact independent human approval required';
 END IF;
 IF (TG_TABLE_NAME='ago_oos_mode_events' AND a.requester_id<>NEW.actor_id)
    OR (TG_TABLE_NAME='ago_marketplace_assets' AND a.requester_id<>NEW.publisher_id)
    OR (TG_TABLE_NAME='ago_asset_consumptions' AND a.requester_id<>NEW.actor_id) THEN
   RAISE EXCEPTION 'Requesting actor must match approved identity';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_oos_review_before_insert BEFORE INSERT ON ago_oos_mode_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
CREATE TRIGGER ago_budget_review_before_insert BEFORE INSERT ON ago_budget_envelopes
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
CREATE TRIGGER ago_marketplace_review_before_write BEFORE INSERT OR UPDATE ON ago_marketplace_assets
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
CREATE TRIGGER ago_marketplace_use_before_insert BEFORE INSERT ON ago_asset_consumptions
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
CREATE TRIGGER ago_costs_pending_before_insert BEFORE INSERT ON ago_observed_costs
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
CREATE TRIGGER ago_evolution_pending_before_insert BEFORE INSERT ON ago_evolution_observations
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
CREATE TRIGGER ago_twin_uncalibrated_before_insert BEFORE INSERT ON ago_twin_scenarios
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_write_guard();
