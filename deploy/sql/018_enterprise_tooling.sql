-- M8 governed enterprise tool registration, automation and immutable execution evidence.
CREATE TABLE ago_tool_enrollments (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 tool_code text NOT NULL CHECK
  (tool_code IN ('tool:scorecard','tool:knowledge_digest','tool:external_metrics')),
 proposer_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'proposed'
   CHECK (status IN ('proposed','active','rejected','disabled')),
 created_at timestamptz NOT NULL DEFAULT now(),
 changed_at timestamptz,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY (tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((status='proposed' AND changed_at IS NULL)
  OR (status<>'proposed' AND changed_at IS NOT NULL))
);
CREATE UNIQUE INDEX ago_one_current_tool_enrollment
 ON ago_tool_enrollments(tenant_id,tool_code)
 WHERE status IN ('proposed','active');
CREATE INDEX ago_tools_tenant ON ago_tool_enrollments(tenant_id,created_at DESC,id);

CREATE TABLE ago_tool_enrollment_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 enrollment_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 event text NOT NULL CHECK (event IN ('proposed','active','rejected','disabled')),
 rationale text NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 3000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY (tenant_id,enrollment_id) REFERENCES ago_tool_enrollments(tenant_id,id),
 FOREIGN KEY (tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TRIGGER ago_tool_enrollment_audit_immutable BEFORE UPDATE OR DELETE
 ON ago_tool_enrollment_audit FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_automation_rules (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 creator_id uuid NOT NULL,
 department_id uuid NOT NULL,
 assignee_id uuid NOT NULL,
 tool_code text NOT NULL CHECK
  (tool_code IN ('tool:scorecard','tool:knowledge_digest','tool:external_metrics')),
 trigger_kind text NOT NULL CHECK
  (trigger_kind IN ('qa_pass','knowledge_verified')),
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
 created_at timestamptz NOT NULL DEFAULT now(),
 disabled_at timestamptz,
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,creator_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY (tenant_id,assignee_id) REFERENCES ago_employees(tenant_id,id),
 CHECK ((status='active' AND disabled_at IS NULL) OR
   (status='disabled' AND disabled_at IS NOT NULL))
);
CREATE INDEX ago_automation_active_rules ON ago_automation_rules(tenant_id,status);

CREATE TABLE ago_automation_firings (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 rule_id uuid NOT NULL,
 source_id uuid NOT NULL,
 task_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,rule_id,source_id),
 UNIQUE(tenant_id,task_id),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY (tenant_id,rule_id) REFERENCES ago_automation_rules(tenant_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE TRIGGER ago_automation_firing_immutable BEFORE UPDATE OR DELETE
 ON ago_automation_firings FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_tool_runs (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 task_id uuid NOT NULL,
 tool_code text NOT NULL CHECK
  (tool_code IN ('tool:scorecard','tool:knowledge_digest','tool:external_metrics')),
 executor_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'running' CHECK
  (status IN ('running','completed','failed','uncertain')),
 output jsonb,
 failure_code text,
 started_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,task_id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,executor_id) REFERENCES ago_users(tenant_id,id),
 CHECK ((status='running' AND finished_at IS NULL AND failure_code IS NULL)
  OR (status IN ('completed','failed','uncertain') AND finished_at IS NOT NULL))
);
CREATE INDEX ago_tool_runs_tenant_time ON ago_tool_runs(tenant_id,started_at DESC);
CREATE TABLE ago_tool_run_evidence (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 run_id uuid NOT NULL,
 event text NOT NULL CHECK (event IN ('claimed','completed','failed','uncertain')),
 note text NOT NULL CHECK (length(trim(note)) BETWEEN 1 AND 2000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY (tenant_id,run_id) REFERENCES ago_tool_runs(tenant_id,id)
);
CREATE TRIGGER ago_tool_evidence_immutable BEFORE UPDATE OR DELETE
 ON ago_tool_run_evidence FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE OR REPLACE FUNCTION ago_guard_tool_enrollment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approved text;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Tool enrollments cannot be deleted'; END IF;
 IF (OLD.id,OLD.tenant_id,OLD.tool_code,OLD.proposer_id,OLD.approval_id,
     OLD.created_at) IS DISTINCT FROM
    (NEW.id,NEW.tenant_id,NEW.tool_code,NEW.proposer_id,NEW.approval_id,
     NEW.created_at)
 THEN RAISE EXCEPTION 'Tool enrollment metadata is immutable'; END IF;
 IF OLD.status='proposed' AND NEW.status IN ('active','rejected')
   AND NEW.changed_at IS NOT NULL THEN
   SELECT status INTO approved FROM ago_approval_requests
    WHERE tenant_id=OLD.tenant_id AND id=OLD.approval_id
    AND action='tool:enroll:' || OLD.id::text;
   IF (NEW.status='active' AND approved='approved')
      OR (NEW.status='rejected' AND approved='rejected') THEN RETURN NEW; END IF;
 END IF;
 IF OLD.status='active' AND NEW.status='disabled' AND NEW.changed_at IS NOT NULL
 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Invalid enrollment transition or missing human approval';
END;
$$;
CREATE TRIGGER ago_tool_enrollment_integrity BEFORE UPDATE OR DELETE
 ON ago_tool_enrollments FOR EACH ROW EXECUTE FUNCTION ago_guard_tool_enrollment();

CREATE OR REPLACE FUNCTION ago_guard_automation_rule() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='active' AND NEW.status='disabled'
  AND NEW.disabled_at IS NOT NULL
  AND (OLD.id,OLD.tenant_id,OLD.creator_id,OLD.department_id,OLD.assignee_id,
       OLD.tool_code,OLD.trigger_kind,OLD.created_at) IS NOT DISTINCT FROM
      (NEW.id,NEW.tenant_id,NEW.creator_id,NEW.department_id,NEW.assignee_id,
       NEW.tool_code,NEW.trigger_kind,NEW.created_at) THEN
    RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Automation rules are immutable except disabling';
END;
$$;
CREATE TRIGGER ago_automation_rule_integrity BEFORE UPDATE OR DELETE
 ON ago_automation_rules FOR EACH ROW EXECUTE FUNCTION ago_guard_automation_rule();

CREATE OR REPLACE FUNCTION ago_guard_tool_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='running'
  AND NEW.status IN ('completed','failed','uncertain')
  AND NEW.finished_at IS NOT NULL
  AND (OLD.id,OLD.tenant_id,OLD.task_id,OLD.tool_code,OLD.executor_id,
       OLD.started_at) IS NOT DISTINCT FROM
      (NEW.id,NEW.tenant_id,NEW.task_id,NEW.tool_code,NEW.executor_id,
       NEW.started_at) THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Tool run history is immutable';
END;
$$;
CREATE TRIGGER ago_tool_run_integrity BEFORE UPDATE OR DELETE
 ON ago_tool_runs FOR EACH ROW EXECUTE FUNCTION ago_guard_tool_run();
