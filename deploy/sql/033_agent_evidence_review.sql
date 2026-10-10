-- Section 22: human-reviewed, evidence-linked *operational* agent competencies.
-- This is not consciousness, clinical stress, trusted source certification
-- or a way for an AI to grant itself new permissions.
CREATE TABLE ago_agent_evidence_intents (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 employee_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN (
  'skill','knowledge','confidence','risk','learning','permission_awareness')),
 label text NOT NULL CHECK(length(trim(label)) BETWEEN 1 AND 160),
 value_int integer CHECK(value_int BETWEEN 0 AND 100),
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 note text NOT NULL CHECK(length(trim(note)) BETWEEN 1 AND 2000),
 canonical_payload text NOT NULL CHECK(length(canonical_payload) BETWEEN 20 AND 5000),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((kind='confidence' AND value_int IS NOT NULL)
     OR (kind<>'confidence' AND value_int IS NULL))
);
CREATE TABLE ago_agent_evidence_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 intent_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 applied_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),UNIQUE(tenant_id,intent_id),UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES ago_agent_evidence_intents(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 FOREIGN KEY(tenant_id,applied_by) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_agent_evidence_history
 ON ago_agent_evidence_intents(tenant_id,employee_id,created_at DESC,id);

CREATE FUNCTION ago_agent_evidence_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record; k text;
BEGIN
 SELECT kind INTO k FROM ago_employees
 WHERE tenant_id=NEW.tenant_id AND id=NEW.employee_id;
 SELECT action,status,requester_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF k IS DISTINCT FROM 'ai' OR NOT FOUND OR
   a.status IS DISTINCT FROM 'pending' OR
   a.requester_id IS DISTINCT FROM NEW.actor_id OR
   a.action IS DISTINCT FROM ('enterprise:agent-evidence:'||
     NEW.employee_id::text||':'||NEW.digest) OR
   NEW.digest IS DISTINCT FROM encode(sha256(convert_to(NEW.canonical_payload,'UTF8')),'hex')
 THEN RAISE EXCEPTION 'Exact pending independent employee evidence review required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_agent_evidence_intent_insert BEFORE INSERT ON ago_agent_evidence_intents
 FOR EACH ROW EXECUTE FUNCTION ago_agent_evidence_intent_guard();
CREATE TRIGGER ago_agent_evidence_intent_immutable BEFORE UPDATE OR DELETE ON ago_agent_evidence_intents
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE FUNCTION ago_agent_evidence_apply_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; a record;
BEGIN
 SELECT employee_id,actor_id,approval_id INTO p FROM ago_agent_evidence_intents
 WHERE tenant_id=NEW.tenant_id AND id=NEW.intent_id;
 SELECT status,requester_id,reviewer_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF p.approval_id IS DISTINCT FROM NEW.approval_id
 OR p.actor_id IS DISTINCT FROM NEW.applied_by
 OR a.status IS DISTINCT FROM 'approved'
 OR a.requester_id IS DISTINCT FROM NEW.applied_by OR a.reviewer_id IS NULL
 OR a.reviewer_id=a.requester_id
 THEN RAISE EXCEPTION 'Independent evidence decision is missing'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_agent_evidence_review BEFORE INSERT ON ago_agent_evidence_events
 FOR EACH ROW EXECUTE FUNCTION ago_agent_evidence_apply_guard();
CREATE TRIGGER ago_agent_evidence_events_immutable BEFORE UPDATE OR DELETE ON ago_agent_evidence_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
