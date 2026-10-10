-- Section 22 operational assistance and Section 23 governed plan outcome lineage.
-- Additive only: live founder data is not migrated by GitHub CI.
CREATE TABLE ago_employee_help_requests (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 employee_id uuid NOT NULL,
 task_id uuid,
 submitted_by uuid NOT NULL,
 reason text NOT NULL CHECK(reason IN
  ('overload','low_confidence','missing_permission','dependency','safety_risk','assistance')),
 severity text NOT NULL CHECK(severity IN ('advisory','blocking')),
 summary text NOT NULL CHECK(length(trim(summary)) BETWEEN 1 AND 1500),
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,submitted_by) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_employee_help_open_idx ON ago_employee_help_requests(tenant_id,employee_id,created_at DESC);

CREATE TABLE ago_employee_help_decisions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 request_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 outcome text NOT NULL CHECK(outcome IN ('resolved','rejected')),
 explanation text NOT NULL CHECK(length(trim(explanation)) BETWEEN 1 AND 1500),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,request_id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,request_id) REFERENCES ago_employee_help_requests(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);

CREATE FUNCTION ago_help_decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a
 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.status<>'approved'
    OR a.action<>'enterprise:help:resolve:'||NEW.request_id::text
    OR a.requester_id<>NEW.actor_id
    OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id
 THEN RAISE EXCEPTION 'Exact independent human assistance approval required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_help_decision_approved BEFORE INSERT ON ago_employee_help_decisions
 FOR EACH ROW EXECUTE FUNCTION ago_help_decision_guard();
CREATE TRIGGER ago_help_request_immutable BEFORE UPDATE OR DELETE ON ago_employee_help_requests
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER ago_help_decision_immutable BEFORE UPDATE OR DELETE ON ago_employee_help_decisions
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

-- A genuine blocking assistance request stops NEW task/agent executions until
-- separately reviewed and independently approved. Existing running attempts
-- are not silently killed or mutated; operator must inspect them.
CREATE FUNCTION ago_help_execution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE employee uuid; tenant uuid;
BEGIN
 IF NEW.status<>'running' THEN RETURN NEW; END IF;
 IF TG_TABLE_NAME='ago_governed_tasks' THEN
   IF TG_OP='UPDATE' AND OLD.status='running' THEN RETURN NEW; END IF;
   employee:=NEW.assignee_id; tenant:=NEW.tenant_id;
 ELSE
   employee:=NEW.agent_id; tenant:=NEW.tenant_id;
 END IF;
 IF EXISTS (
   SELECT 1 FROM ago_employee_help_requests h
   WHERE h.tenant_id=tenant AND h.employee_id=employee
     AND h.severity='blocking'
     AND NOT EXISTS (SELECT 1 FROM ago_employee_help_decisions d
       WHERE d.tenant_id=h.tenant_id AND d.request_id=h.id AND d.outcome='resolved')
 ) THEN RAISE EXCEPTION 'Blocking assistance must be independently resolved before execution'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_governed_task_help_guard BEFORE INSERT OR UPDATE ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_help_execution_guard();
CREATE TRIGGER ago_agent_run_help_guard BEFORE INSERT ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_help_execution_guard();

CREATE TABLE ago_horizon_task_links (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 horizon_plan_id uuid NOT NULL,
 task_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,horizon_plan_id,task_id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,horizon_plan_id) REFERENCES ago_horizon_plans(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE FUNCTION ago_horizon_task_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a
 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.status<>'approved'
 OR a.action <> 'enterprise:plan-task:'||NEW.horizon_plan_id::text||':'||NEW.task_id::text
 OR a.requester_id<>NEW.actor_id
 OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id
 THEN RAISE EXCEPTION 'Plan-to-task lineage needs independent approval'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_horizon_task_link_approved BEFORE INSERT ON ago_horizon_task_links
 FOR EACH ROW EXECUTE FUNCTION ago_horizon_task_link_guard();
CREATE TRIGGER ago_horizon_task_link_immutable BEFORE UPDATE OR DELETE ON ago_horizon_task_links
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE INDEX ago_horizon_task_link_history ON ago_horizon_task_links(tenant_id,horizon_plan_id,created_at DESC);
