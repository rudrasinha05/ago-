-- Additive Sections 21–27 evidence. No existing source or approval is rewritten.
CREATE TABLE ago_enterprise_evidence (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 actor_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN
  ('operations','planning','competence','finance','diagnostics','twin_state',
   'forecast','calibration','experiment','intent','intent_result')),
 operation_key text NOT NULL CHECK(length(trim(operation_key)) BETWEEN 1 AND 160),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,kind,operation_key),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_enterprise_evidence_latest ON ago_enterprise_evidence
 (tenant_id,kind,created_at DESC,id);
CREATE TRIGGER ago_enterprise_evidence_immutable
 BEFORE UPDATE OR DELETE ON ago_enterprise_evidence
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

-- Every reviewed evidence decision binds the complete immutable digest.
CREATE TABLE ago_enterprise_evidence_reviews (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 evidence_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,evidence_id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,evidence_id) REFERENCES ago_enterprise_evidence(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE TRIGGER ago_enterprise_evidence_review_immutable
 BEFORE UPDATE OR DELETE ON ago_enterprise_evidence_reviews
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE FUNCTION ago_enterprise_evidence_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approval record; item record;
BEGIN
 SELECT * INTO item FROM ago_enterprise_evidence
  WHERE tenant_id=NEW.tenant_id AND id=NEW.evidence_id;
 SELECT * INTO approval FROM ago_approval_requests
  WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF approval.status IS DISTINCT FROM 'approved'
  OR approval.requester_id IS DISTINCT FROM NEW.actor_id
  OR approval.reviewer_id IS NULL OR approval.reviewer_id=NEW.actor_id
  OR approval.action IS DISTINCT FROM
     ('enterprise:evidence:' || item.id::text || ':' || item.digest)
 THEN RAISE EXCEPTION 'Independent exact-digest evidence review required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_enterprise_review_authority
 BEFORE INSERT ON ago_enterprise_evidence_reviews
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_evidence_review_guard();

-- QA evidence time records the actual insert, even in a long operator transaction.
ALTER TABLE ago_task_reviews ALTER COLUMN created_at SET DEFAULT clock_timestamp();
