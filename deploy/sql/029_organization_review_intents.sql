-- AGO Section 21: bind independent HR/department approval to the entire intent.
-- Migration 029 is additive. Existing historical personnel events stay untouched.
-- PostgreSQL 14+ built-in SHA-256 bytea function; no new extensions or services.
CREATE TABLE ago_organization_review_intents (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 approval_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 target_id uuid NOT NULL,
 change_kind text NOT NULL CHECK(change_kind IN ('hired','promoted','terminated','created','closed')),
 payload_key text NOT NULL CHECK(length(payload_key) BETWEEN 20 AND 5000),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 CHECK(payload_key::jsonb=payload)
);
CREATE INDEX ago_org_review_target ON ago_organization_review_intents(tenant_id,target_id,created_at DESC);

CREATE FUNCTION ago_org_review_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record;
BEGIN
 SELECT action,status,requester_id INTO a FROM ago_approval_requests
  WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.status<>'pending' OR a.requester_id<>NEW.actor_id
 OR a.action <> ('enterprise:'||
     CASE WHEN NEW.change_kind IN ('created','closed') THEN 'department' ELSE 'hr' END||
     ':'||NEW.change_kind||':'||NEW.target_id::text||':'||NEW.digest)
 OR NEW.payload->>'change_kind' IS DISTINCT FROM NEW.change_kind
 OR NEW.payload->>'target_id' IS DISTINCT FROM NEW.target_id::text
 OR NEW.payload->>'reason' IS NULL
 OR NEW.digest IS DISTINCT FROM encode(sha256(convert_to(NEW.payload_key,'UTF8')),'hex')
 THEN RAISE EXCEPTION 'Full immutable organizational intent required before human review'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_org_intent_review BEFORE INSERT ON ago_organization_review_intents
 FOR EACH ROW EXECUTE FUNCTION ago_org_review_intent_guard();
CREATE TRIGGER ago_org_intent_immutable BEFORE UPDATE OR DELETE ON ago_organization_review_intents
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

-- Preserve all earlier promotion/termination safeguards while demanding the
-- reviewer-approved name, department, manager, level and reason be unchanged.
CREATE OR REPLACE FUNCTION ago_personnel_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record; intent record; last_event record; person record;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a FROM ago_approval_requests
  WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 SELECT digest,payload INTO intent FROM ago_organization_review_intents
  WHERE tenant_id=NEW.tenant_id AND approval_id=NEW.approval_id
    AND target_id=NEW.employee_id AND change_kind=NEW.change_kind;
 IF NOT FOUND THEN RAISE EXCEPTION 'Pre-reviewed exact AI personnel payload missing'; END IF;
 IF a.action IS DISTINCT FROM ('enterprise:hr:'||NEW.change_kind||':'||
       NEW.employee_id::text||':'||intent.digest)
 OR a.status IS DISTINCT FROM 'approved'
 OR a.requester_id IS DISTINCT FROM NEW.actor_id
 OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id
 OR intent.payload->>'reason' IS DISTINCT FROM NEW.reason
 THEN RAISE EXCEPTION 'Exact independent personnel approval required'; END IF;
 SELECT id,kind,department_id,name,manager_id INTO person FROM ago_employees
 WHERE tenant_id=NEW.tenant_id AND id=NEW.employee_id;
 IF person.kind IS DISTINCT FROM 'ai' THEN
   RAISE EXCEPTION 'Only registered AI workers may use automated HR'; END IF;
 IF NEW.change_kind='hired' AND (
   person.department_id::text IS DISTINCT FROM intent.payload->>'department_id' OR
   person.name IS DISTINCT FROM intent.payload->>'name' OR
   person.manager_id::text IS DISTINCT FROM intent.payload->>'manager_id' OR
   NEW.role_level<>1
 ) THEN RAISE EXCEPTION 'Hired identity differs from independent HR review'; END IF;
 IF NEW.change_kind='promoted' AND
   NEW.role_level IS DISTINCT FROM (intent.payload->>'role_level')::int THEN
   RAISE EXCEPTION 'Promotion level differs from reviewed intent'; END IF;
 SELECT change_kind,role_level INTO last_event FROM ago_personnel_events
 WHERE tenant_id=NEW.tenant_id AND employee_id=NEW.employee_id
 ORDER BY created_at DESC,id DESC LIMIT 1;
 IF FOUND AND last_event.change_kind='terminated' THEN
   RAISE EXCEPTION 'Terminated worker cannot be reactivated'; END IF;
 IF NEW.change_kind='hired' AND FOUND THEN
   RAISE EXCEPTION 'AI worker may be hired once';
 ELSIF NEW.change_kind='promoted' AND
   NEW.role_level<=coalesce(last_event.role_level,1) THEN
   RAISE EXCEPTION 'Promotion must strictly increase role';
 ELSIF NEW.change_kind='terminated' AND EXISTS(
   SELECT 1 FROM ago_governed_tasks WHERE tenant_id=NEW.tenant_id
   AND assignee_id=NEW.employee_id AND status='running'
 ) THEN RAISE EXCEPTION 'Finish or reconcile in-flight tasks before termination'; END IF;
 RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION ago_department_change_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record; intent record; department_name text;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 SELECT digest,payload INTO intent FROM ago_organization_review_intents
 WHERE tenant_id=NEW.tenant_id AND approval_id=NEW.approval_id
   AND target_id=NEW.department_id AND change_kind=NEW.action;
 IF NOT FOUND THEN RAISE EXCEPTION 'Pre-reviewed exact department intent missing'; END IF;
 IF a.action IS DISTINCT FROM ('enterprise:department:'||NEW.action||':'||
       NEW.department_id::text||':'||intent.digest)
 OR a.status IS DISTINCT FROM 'approved'
 OR a.requester_id IS DISTINCT FROM NEW.actor_id
 OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id
 OR intent.payload->>'reason' IS DISTINCT FROM NEW.reason
 THEN RAISE EXCEPTION 'Exact independent department approval required'; END IF;
 IF NEW.action='created' THEN
   SELECT name INTO department_name FROM ago_departments
     WHERE tenant_id=NEW.tenant_id AND id=NEW.department_id;
   IF department_name IS DISTINCT FROM intent.payload->>'name' THEN
     RAISE EXCEPTION 'Department name differs from approved intent'; END IF;
 ELSIF EXISTS(
   SELECT 1 FROM ago_employees
   WHERE tenant_id=NEW.tenant_id AND department_id=NEW.department_id
 ) THEN RAISE EXCEPTION 'Nonempty department cannot close'; END IF;
 RETURN NEW;
END;
$$;
