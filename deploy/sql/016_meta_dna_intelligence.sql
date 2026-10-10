-- M7: immutable organizational DNA, executive evidence and human-reviewed Meta Brain.
CREATE TABLE ago_dna_versions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 version integer NOT NULL CHECK (version > 0),
 proposer_id uuid NOT NULL,
 profile jsonb NOT NULL CHECK (jsonb_typeof(profile)='object'),
 rationale text NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 3000),
 approval_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','active','superseded','rejected')),
 activated_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,version),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY (tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((status IN ('proposed','rejected') AND activated_at IS NULL)
     OR (status IN ('active','superseded') AND activated_at IS NOT NULL))
);
CREATE UNIQUE INDEX ago_one_active_dna_per_tenant
 ON ago_dna_versions(tenant_id) WHERE status='active';
CREATE INDEX idx_ago_dna_tenant_version ON ago_dna_versions(tenant_id,version DESC);

CREATE TABLE ago_executive_snapshots (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 analyst_id uuid NOT NULL,
 dna_id uuid,
 metrics jsonb NOT NULL CHECK (jsonb_typeof(metrics)='object'),
 risk_flags jsonb NOT NULL CHECK (jsonb_typeof(risk_flags)='array'),
 fitness numeric(5,2) CHECK (fitness BETWEEN 0 AND 100),
 digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY (tenant_id,analyst_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,dna_id) REFERENCES ago_dna_versions(tenant_id,id)
);
CREATE INDEX idx_ago_executive_snapshots_tenant
 ON ago_executive_snapshots(tenant_id,created_at DESC,id);
CREATE TRIGGER ago_exec_snapshots_immutable
 BEFORE UPDATE OR DELETE ON ago_executive_snapshots
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_meta_recommendations (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 snapshot_id uuid NOT NULL,
 proposer_id uuid NOT NULL,
 category text NOT NULL
  CHECK (category IN ('insufficient_data','qa_below_target',
    'backlog_over_limit','budget_alert','stable_operation')),
 summary text NOT NULL CHECK (length(trim(summary)) BETWEEN 1 AND 2000),
 evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence)='object'),
 approval_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'proposed'
   CHECK (status IN ('proposed','endorsed','rejected')),
 decided_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,snapshot_id,category),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY (tenant_id,snapshot_id)
  REFERENCES ago_executive_snapshots(tenant_id,id),
 FOREIGN KEY (tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id)
  REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((status='proposed' AND decided_at IS NULL)
    OR (status<>'proposed' AND decided_at IS NOT NULL))
);
CREATE INDEX idx_ago_meta_recommendations_tenant
 ON ago_meta_recommendations(tenant_id,created_at DESC,id);

-- No direct profile/status rewriting: exact scoped human M2 decision required.
CREATE OR REPLACE FUNCTION ago_guard_dna_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE decision text;
BEGIN
 IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Organizational DNA versions cannot be deleted';
 END IF;
 IF (OLD.id,OLD.tenant_id,OLD.version,OLD.proposer_id,OLD.profile,
     OLD.rationale,OLD.approval_id,OLD.created_at) IS DISTINCT FROM
    (NEW.id,NEW.tenant_id,NEW.version,NEW.proposer_id,NEW.profile,
     NEW.rationale,NEW.approval_id,NEW.created_at)
 THEN RAISE EXCEPTION 'Organizational DNA content is immutable'; END IF;
 IF OLD.status='active' AND NEW.status='superseded'
   AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at THEN
    RETURN NEW;
 END IF;
 IF OLD.status='proposed' AND NEW.status IN ('active','rejected') THEN
   SELECT status INTO decision FROM ago_approval_requests
   WHERE tenant_id=OLD.tenant_id AND id=OLD.approval_id
     AND action='dna:activate:' || OLD.id::text;
   IF (NEW.status='active' AND decision='approved' AND NEW.activated_at IS NOT NULL)
      OR (NEW.status='rejected' AND decision='rejected'
          AND NEW.activated_at IS NULL) THEN
     RETURN NEW;
   END IF;
 END IF;
 RAISE EXCEPTION 'DNA lifecycle requires scoped independent approval';
END;
$$;
CREATE TRIGGER ago_dna_versions_guard BEFORE UPDATE OR DELETE ON ago_dna_versions
 FOR EACH ROW EXECUTE FUNCTION ago_guard_dna_version();

CREATE OR REPLACE FUNCTION ago_guard_meta_recommendation() RETURNS trigger
 LANGUAGE plpgsql AS $$
DECLARE decision text;
BEGIN
 IF TG_OP='DELETE' THEN
   RAISE EXCEPTION 'Meta Brain proposals cannot be deleted';
 END IF;
 IF (OLD.id,OLD.tenant_id,OLD.snapshot_id,OLD.proposer_id,OLD.category,
     OLD.summary,OLD.evidence,OLD.approval_id,OLD.created_at) IS DISTINCT FROM
    (NEW.id,NEW.tenant_id,NEW.snapshot_id,NEW.proposer_id,NEW.category,
     NEW.summary,NEW.evidence,NEW.approval_id,NEW.created_at)
 THEN RAISE EXCEPTION 'Meta Brain evidence is immutable'; END IF;
 IF OLD.status='proposed' AND NEW.status IN ('endorsed','rejected')
    AND NEW.decided_at IS NOT NULL THEN
   SELECT status INTO decision FROM ago_approval_requests
   WHERE tenant_id=OLD.tenant_id AND id=OLD.approval_id
     AND action='meta:endorse:' || OLD.id::text;
   IF (NEW.status='endorsed' AND decision='approved')
       OR (NEW.status='rejected' AND decision='rejected') THEN
     RETURN NEW;
   END IF;
 END IF;
 RAISE EXCEPTION 'Recommendation transition requires human approval decision';
END;
$$;
CREATE TRIGGER ago_meta_recommendations_guard
 BEFORE UPDATE OR DELETE ON ago_meta_recommendations
 FOR EACH ROW EXECUTE FUNCTION ago_guard_meta_recommendation();
