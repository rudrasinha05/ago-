-- Additive personal-localhost lifecycle, prospective experiments and documents.
ALTER TABLE ago_enterprise_evidence DROP CONSTRAINT ago_enterprise_evidence_kind_check;
ALTER TABLE ago_enterprise_evidence ADD CONSTRAINT ago_enterprise_evidence_kind_check
 CHECK(kind IN ('operations','planning','competence','finance','diagnostics','twin_state',
 'forecast','calibration','experiment','intent','intent_result','lifecycle','experiment_registration',
 'experiment_measurement','financial_document','reconciliation','evolution_policy_audit'));

CREATE TABLE ago_experiment_assignments (
 tenant_id uuid NOT NULL,
 task_id uuid NOT NULL,
 registration_id uuid NOT NULL,
 variant text NOT NULL CHECK(variant IN ('baseline','candidate')),
 PRIMARY KEY(tenant_id,task_id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,registration_id) REFERENCES ago_enterprise_evidence(tenant_id,id)
);
CREATE TRIGGER ago_experiment_assignment_immutable BEFORE UPDATE OR DELETE
 ON ago_experiment_assignments FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE TABLE ago_financial_matches (
 tenant_id uuid NOT NULL,
 invoice_document_id uuid NOT NULL,
 bank_document_id uuid NOT NULL,
 reconciliation_id uuid NOT NULL,
 cost_id uuid NOT NULL,
 invoice_digest text NOT NULL CHECK(invoice_digest ~ '^[a-f0-9]{64}$'),
 bank_digest text NOT NULL CHECK(bank_digest ~ '^[a-f0-9]{64}$'),
 PRIMARY KEY(tenant_id,invoice_document_id),
 UNIQUE(tenant_id,bank_document_id),
 UNIQUE(tenant_id,cost_id), UNIQUE(tenant_id,invoice_digest), UNIQUE(tenant_id,bank_digest),
 FOREIGN KEY(tenant_id,cost_id) REFERENCES ago_observed_costs(tenant_id,id),
 FOREIGN KEY(tenant_id,invoice_document_id) REFERENCES ago_enterprise_evidence(tenant_id,id),
 FOREIGN KEY(tenant_id,bank_document_id) REFERENCES ago_enterprise_evidence(tenant_id,id),
 FOREIGN KEY(tenant_id,reconciliation_id) REFERENCES ago_enterprise_evidence(tenant_id,id)
);
CREATE TRIGGER ago_financial_match_immutable BEFORE UPDATE OR DELETE
 ON ago_financial_matches FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE FUNCTION ago_experiment_assignment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item record; task record;
BEGIN
 SELECT * INTO item FROM ago_enterprise_evidence WHERE tenant_id=NEW.tenant_id AND id=NEW.registration_id;
 SELECT * INTO task FROM ago_governed_tasks WHERE tenant_id=NEW.tenant_id AND id=NEW.task_id FOR UPDATE;
 IF item.kind IS DISTINCT FROM 'experiment_registration'
  OR item.payload->'intent'->'assignment'->>NEW.task_id::text IS DISTINCT FROM NEW.variant
  OR task.status NOT IN ('proposed','waiting_approval') OR task.action IS DISTINCT FROM 'internal:brief'
  OR EXISTS(SELECT 1 FROM ago_agent_runs WHERE tenant_id=NEW.tenant_id AND task_id=NEW.task_id)
  OR EXISTS(SELECT 1 FROM ago_task_reviews WHERE tenant_id=NEW.tenant_id AND task_id=NEW.task_id)
 THEN RAISE EXCEPTION 'Prospective exact registration assignment required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_experiment_assignment_authority BEFORE INSERT ON ago_experiment_assignments
 FOR EACH ROW EXECUTE FUNCTION ago_experiment_assignment_guard();

CREATE FUNCTION ago_experiment_start_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status='running' AND EXISTS(
  SELECT 1 FROM ago_experiment_assignments a WHERE a.tenant_id=NEW.tenant_id AND a.task_id=NEW.id
   AND NOT EXISTS(SELECT 1 FROM ago_enterprise_evidence_reviews r
     WHERE r.tenant_id=a.tenant_id AND r.evidence_id=a.registration_id))
 THEN RAISE EXCEPTION 'Independent prospective experiment review required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_experiment_execution_authority BEFORE UPDATE OF status ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_experiment_start_guard();

-- Review cannot be laundered through a second requester's approval of one's own evidence.
CREATE OR REPLACE FUNCTION ago_enterprise_evidence_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approval record; item record;
BEGIN
 SELECT * INTO item FROM ago_enterprise_evidence WHERE tenant_id=NEW.tenant_id AND id=NEW.evidence_id;
 SELECT * INTO approval FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF approval.status IS DISTINCT FROM 'approved'
  OR approval.requester_id IS DISTINCT FROM NEW.actor_id
  OR item.actor_id IS DISTINCT FROM NEW.actor_id
  OR approval.reviewer_id IS NULL OR approval.reviewer_id=item.actor_id
  OR approval.action IS DISTINCT FROM ('enterprise:evidence:' || item.id::text || ':' || item.digest)
 THEN RAISE EXCEPTION 'Independent exact-digest evidence review required'; END IF;
 RETURN NEW;
END;
$$;
