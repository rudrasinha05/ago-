-- Guard historical review payloads against privileged direct-SQL field substitution.
-- Uses additive 035, without rewriting migrations 033/034.
CREATE OR REPLACE FUNCTION ago_agent_evidence_intent_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE a record; employee_kind text; reviewed jsonb;
BEGIN
 SELECT kind INTO employee_kind FROM ago_employees
 WHERE tenant_id=NEW.tenant_id AND id=NEW.employee_id;
 SELECT action,status,requester_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 reviewed := NEW.canonical_payload::jsonb;
 IF employee_kind IS DISTINCT FROM 'ai'
 OR a.status IS DISTINCT FROM 'pending'
 OR a.requester_id IS DISTINCT FROM NEW.actor_id
 OR a.action IS DISTINCT FROM
     ('enterprise:agent-evidence:'||NEW.employee_id::text||':'||NEW.digest)
 OR NEW.digest IS DISTINCT FROM encode(sha256(convert_to(NEW.canonical_payload,'UTF8')),'hex')
 OR reviewed IS DISTINCT FROM jsonb_build_object(
    'employee_id',NEW.employee_id::text,'kind',NEW.kind,'label',NEW.label,
    'value_int',NEW.value_int,'evidence_ref',NEW.evidence_ref,'note',NEW.note)
 THEN RAISE EXCEPTION 'Exact reviewed employee evidence fields required'; END IF;
 RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION ago_horizon_replan_intent_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE a record; reviewed jsonb;
BEGIN
 SELECT action,status,requester_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 reviewed := NEW.canonical_payload::jsonb;
 IF a.status IS DISTINCT FROM 'pending'
 OR a.requester_id IS DISTINCT FROM NEW.actor_id
 OR a.action IS DISTINCT FROM
     ('enterprise:plan-revise:'||NEW.horizon_plan_id::text||':'||NEW.digest)
 OR NEW.digest IS DISTINCT FROM encode(sha256(convert_to(NEW.canonical_payload,'UTF8')),'hex')
 OR reviewed->>'plan_id' IS DISTINCT FROM NEW.horizon_plan_id::text
 OR (reviewed->>'base_revision')::int IS DISTINCT FROM NEW.base_revision
 OR reviewed->>'title' IS DISTINCT FROM NEW.title
 OR (reviewed->>'starts_at')::timestamptz IS DISTINCT FROM NEW.starts_at
 OR (reviewed->>'ends_at')::timestamptz IS DISTINCT FROM NEW.ends_at
 OR (reviewed->>'budget_ceiling')::numeric IS DISTINCT FROM NEW.budget_ceiling
 OR reviewed->>'evidence_ref' IS DISTINCT FROM NEW.evidence_ref
 OR reviewed->>'rationale' IS DISTINCT FROM NEW.rationale
 OR (SELECT count(*) FROM jsonb_object_keys(reviewed))<>8
 THEN RAISE EXCEPTION 'Exact immutable plan proposal fields required'; END IF;
 RETURN NEW;
END;
$$;
