-- Sections 16/19/20: additive governed records and scoped cultural DNA.
ALTER TABLE ago_executive_snapshots ALTER COLUMN created_at SET DEFAULT clock_timestamp();
ALTER TABLE ago_dna_versions ADD COLUMN charter jsonb NOT NULL DEFAULT '{}'::jsonb
 CHECK (jsonb_typeof(charter)='object');
ALTER TABLE ago_dna_versions ADD COLUMN scope_kind text NOT NULL DEFAULT 'company'
 CHECK (scope_kind IN ('company','department','employee'));
ALTER TABLE ago_dna_versions ADD COLUMN scope_id uuid;
ALTER TABLE ago_dna_versions ADD CONSTRAINT ago_dna_scope_target
 CHECK ((scope_kind='company' AND scope_id IS NULL)
     OR (scope_kind<>'company' AND scope_id IS NOT NULL));
DROP INDEX ago_one_active_dna_per_tenant;
CREATE UNIQUE INDEX ago_one_active_company_dna ON ago_dna_versions(tenant_id)
 WHERE status='active' AND scope_kind='company';
CREATE UNIQUE INDEX ago_one_active_scoped_dna
 ON ago_dna_versions(tenant_id,scope_kind,scope_id)
 WHERE status='active' AND scope_kind<>'company';
CREATE INDEX ago_dna_scope_lookup ON ago_dna_versions(tenant_id,scope_kind,scope_id,version DESC);

CREATE FUNCTION ago_validate_dna_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent jsonb; dept uuid; dept_profile jsonb;
BEGIN
 IF TG_OP='INSERT' AND NEW.status<>'proposed' THEN
   RAISE EXCEPTION 'DNA must start as a proposal';
 END IF;
 IF TG_OP='UPDATE' AND (OLD.charter,OLD.scope_kind,OLD.scope_id)
   IS DISTINCT FROM (NEW.charter,NEW.scope_kind,NEW.scope_id) THEN
   RAISE EXCEPTION 'DNA scope and philosophy are immutable';
 END IF;
 IF TG_OP='UPDATE' AND NOT (OLD.status='proposed' AND NEW.status='active') THEN
   RETURN NEW;
 END IF;
 IF (SELECT count(*) FROM jsonb_object_keys(NEW.profile))<>3
    OR NOT NEW.profile ?& ARRAY['qa_target_pct','backlog_limit','budget_alert_pct']
    OR EXISTS (SELECT 1 FROM jsonb_each(NEW.profile) v WHERE jsonb_typeof(v.value)<>'number')
    OR (NEW.profile->>'qa_target_pct') !~ '^[0-9]+$'
    OR (NEW.profile->>'backlog_limit') !~ '^[0-9]+$'
    OR (NEW.profile->>'budget_alert_pct') !~ '^[0-9]+$'
    OR (NEW.profile->>'qa_target_pct')::numeric NOT BETWEEN 50 AND 100
    OR (NEW.profile->>'backlog_limit')::numeric NOT BETWEEN 0 AND 10000
    OR (NEW.profile->>'budget_alert_pct')::numeric NOT BETWEEN 1 AND 100 THEN
   RAISE EXCEPTION 'Invalid bounded DNA thresholds';
 END IF;
 IF EXISTS (SELECT 1 FROM jsonb_each(NEW.charter) c WHERE jsonb_typeof(c.value)<>'string'
        OR length(trim(c.value #>> '{}')) NOT BETWEEN 1 AND 2000) THEN
   RAISE EXCEPTION 'Invalid DNA philosophy';
 END IF;
 IF NEW.scope_kind='company' THEN
   IF NEW.charter<>'{}'::jsonb AND ((SELECT count(*) FROM jsonb_object_keys(NEW.charter))<>18
    OR NOT NEW.charter ?& ARRAY['mission','vision','values','leadership_style',
     'engineering_culture','research_culture','decision_philosophy','communication_style',
     'innovation_philosophy','risk_appetite','documentation_philosophy','security_philosophy',
     'hiring_philosophy','promotion_philosophy','meeting_philosophy',
     'conflict_resolution_philosophy','learning_philosophy','quality_philosophy']) THEN
     RAISE EXCEPTION 'Company DNA requires all philosophies';
   END IF;
   RETURN NEW;
 END IF;
 IF EXISTS (SELECT 1 FROM jsonb_object_keys(NEW.charter) k
    WHERE k NOT IN ('communication_style','documentation_philosophy',
                   'meeting_philosophy','learning_philosophy')) THEN
   RAISE EXCEPTION 'Protected company philosophy cannot be overridden';
 END IF;
 IF NEW.scope_kind='employee' THEN
   SELECT department_id INTO dept FROM ago_employees
     WHERE tenant_id=NEW.tenant_id AND id=NEW.scope_id;
 ELSE
   SELECT id INTO dept FROM ago_departments
     WHERE tenant_id=NEW.tenant_id AND id=NEW.scope_id;
 END IF;
 IF dept IS NULL THEN RAISE EXCEPTION 'Scoped tenant target missing'; END IF;
 SELECT profile INTO parent FROM ago_dna_versions
   WHERE tenant_id=NEW.tenant_id AND scope_kind='company' AND status='active';
 parent := coalesce(parent,'{"qa_target_pct":85,"backlog_limit":5,"budget_alert_pct":80}'::jsonb);
 IF NEW.scope_kind='employee' THEN
   SELECT profile INTO dept_profile FROM ago_dna_versions WHERE tenant_id=NEW.tenant_id
     AND scope_kind='department' AND scope_id=dept AND status='active';
   IF dept_profile IS NOT NULL
     AND (dept_profile->>'qa_target_pct')::int >= (parent->>'qa_target_pct')::int
     AND (dept_profile->>'backlog_limit')::int <= (parent->>'backlog_limit')::int
     AND (dept_profile->>'budget_alert_pct')::int <= (parent->>'budget_alert_pct')::int THEN
     parent := dept_profile;
   END IF;
 END IF;
 IF (NEW.profile->>'qa_target_pct')::int < (parent->>'qa_target_pct')::int
    OR (NEW.profile->>'backlog_limit')::int > (parent->>'backlog_limit')::int
    OR (NEW.profile->>'budget_alert_pct')::int > (parent->>'budget_alert_pct')::int THEN
   RAISE EXCEPTION 'Child DNA cannot weaken parent';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_dna_scoped_controls BEFORE INSERT OR UPDATE ON ago_dna_versions
 FOR EACH ROW EXECUTE FUNCTION ago_validate_dna_scope();

ALTER TABLE ago_agent_runs ADD COLUMN dna_context jsonb;
CREATE FUNCTION ago_guard_run_dna() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.dna_context IS DISTINCT FROM NEW.dna_context THEN
   RAISE EXCEPTION 'Execution DNA provenance cannot be rewritten';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_run_dna_immutable BEFORE UPDATE ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_guard_run_dna();

CREATE TABLE ago_architecture_changes (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 proposer_id uuid NOT NULL, approval_id uuid NOT NULL,
 change_key text NOT NULL CHECK (change_key ~ '^ARCH-[0-9]{3,8}$'),
 specification jsonb NOT NULL CHECK (jsonb_typeof(specification)='object'),
 status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), decided_at timestamptz,
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,change_key), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((status='proposed' AND decided_at IS NULL) OR (status<>'proposed' AND decided_at IS NOT NULL))
);
CREATE TABLE ago_meta_evaluations (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 recommendation_id uuid NOT NULL, before_id uuid NOT NULL, after_id uuid NOT NULL,
 proposer_id uuid NOT NULL, approval_id uuid NOT NULL,
 change_evidence text NOT NULL CHECK (length(trim(change_evidence)) BETWEEN 1 AND 3000),
 assessment jsonb NOT NULL CHECK (jsonb_typeof(assessment)='object'),
 status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','verified','rejected')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), decided_at timestamptz,
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,recommendation_id) REFERENCES ago_meta_recommendations(tenant_id,id),
 FOREIGN KEY(tenant_id,before_id) REFERENCES ago_executive_snapshots(tenant_id,id),
 FOREIGN KEY(tenant_id,after_id) REFERENCES ago_executive_snapshots(tenant_id,id),
 FOREIGN KEY(tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK (before_id<>after_id),
 CHECK ((status='proposed' AND decided_at IS NULL) OR (status<>'proposed' AND decided_at IS NOT NULL))
);
CREATE INDEX ago_meta_evaluations_history ON ago_meta_evaluations(tenant_id,created_at DESC,id);
CREATE INDEX ago_architecture_changes_history ON ago_architecture_changes(tenant_id,created_at DESC,id);
CREATE FUNCTION ago_guard_reviewed_observation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE decision text; expected text; accepted text;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Review history cannot be deleted'; END IF;
 IF (to_jsonb(OLD)-'status'-'decided_at') IS DISTINCT FROM
    (to_jsonb(NEW)-'status'-'decided_at') THEN
   RAISE EXCEPTION 'Review evidence is immutable';
 END IF;
 IF TG_TABLE_NAME='ago_architecture_changes' THEN
   expected := 'architecture:review:' || OLD.id::text; accepted := 'accepted';
 ELSE
   expected := 'meta:evaluate:' || OLD.id::text; accepted := 'verified';
 END IF;
 SELECT status INTO decision FROM ago_approval_requests
   WHERE tenant_id=OLD.tenant_id AND id=OLD.approval_id AND action=expected;
 IF OLD.status='proposed' AND NEW.decided_at IS NOT NULL AND
   ((NEW.status=accepted AND decision='approved') OR (NEW.status='rejected' AND decision='rejected')) THEN
   RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Exact independently reviewed approval required';
END;
$$;
CREATE TRIGGER ago_architecture_changes_immutable BEFORE UPDATE OR DELETE ON ago_architecture_changes
 FOR EACH ROW EXECUTE FUNCTION ago_guard_reviewed_observation();
CREATE TRIGGER ago_meta_evaluations_immutable BEFORE UPDATE OR DELETE ON ago_meta_evaluations
 FOR EACH ROW EXECUTE FUNCTION ago_guard_reviewed_observation();
CREATE FUNCTION ago_validate_meta_evaluation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE before_order bigint; after_order bigint; endorsed_at timestamptz;
BEGIN
 SELECT capture_order INTO before_order FROM ago_executive_snapshots
   WHERE tenant_id=NEW.tenant_id AND id=NEW.before_id;
 SELECT capture_order INTO after_order FROM ago_executive_snapshots
   WHERE tenant_id=NEW.tenant_id AND id=NEW.after_id;
 SELECT decided_at INTO endorsed_at FROM ago_meta_recommendations
   WHERE tenant_id=NEW.tenant_id AND id=NEW.recommendation_id AND status='endorsed'
     AND snapshot_id=NEW.before_id;
 IF before_order IS NULL OR after_order IS NULL OR after_order<=before_order OR endorsed_at IS NULL
    OR NOT EXISTS (SELECT 1 FROM ago_executive_snapshots
      WHERE tenant_id=NEW.tenant_id AND id=NEW.after_id AND created_at>=endorsed_at) THEN
   RAISE EXCEPTION 'Endorsed recommendation and ordered after evidence required';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_meta_evaluation_sources BEFORE INSERT ON ago_meta_evaluations
 FOR EACH ROW EXECUTE FUNCTION ago_validate_meta_evaluation();

CREATE FUNCTION ago_validate_review_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected text;
BEGIN
 expected := CASE WHEN TG_TABLE_NAME='ago_architecture_changes'
   THEN 'architecture:review:' ELSE 'meta:evaluate:' END || NEW.id::text;
 IF NEW.status<>'proposed' OR NEW.decided_at IS NOT NULL OR NOT EXISTS
   (SELECT 1 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id
     AND action=expected AND requester_id=NEW.proposer_id AND status='pending') THEN
   RAISE EXCEPTION 'New review requires a matching pending approval proposal';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_architecture_proposal_guard BEFORE INSERT ON ago_architecture_changes
 FOR EACH ROW EXECUTE FUNCTION ago_validate_review_proposal();
CREATE TRIGGER ago_evaluation_proposal_guard BEFORE INSERT ON ago_meta_evaluations
 FOR EACH ROW EXECUTE FUNCTION ago_validate_review_proposal();
