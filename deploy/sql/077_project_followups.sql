-- Direct agent follow-up. Evidence is retained; a notification is not execution.
CREATE TABLE ago_project_followups (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 project_id uuid NOT NULL,
 stage text NOT NULL,
 source_key text NOT NULL CHECK(length(source_key) BETWEEN 1 AND 260),
 source_task_id uuid,
 work_task_id uuid,
 owner_id uuid NOT NULL,
 founder_id uuid NOT NULL,
 code text NOT NULL CHECK(length(code) BETWEEN 1 AND 100),
 feedback text NOT NULL CHECK(length(feedback) BETWEEN 1 AND 4000),
 next_action text NOT NULL CHECK(length(next_action) BETWEEN 1 AND 1000),
 status text NOT NULL CHECK(status IN ('assigned','scheduled','blocked','resolved')),
 eligible_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 resolved_at timestamptz,
 UNIQUE(tenant_id,project_id,stage,source_key),
 FOREIGN KEY(tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(tenant_id,project_id,stage)
   REFERENCES ago_founder_intake_stages(tenant_id,intake_id,stage),
 FOREIGN KEY(tenant_id,source_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,work_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,founder_id) REFERENCES ago_users(tenant_id,id),
 CHECK((status='resolved')=(resolved_at IS NOT NULL))
);
CREATE INDEX ago_project_followups_owner ON ago_project_followups(tenant_id,owner_id,status);

CREATE FUNCTION ago_guard_project_followup() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NOT EXISTS (SELECT 1 FROM ago_founder_intakes i
                 WHERE i.tenant_id=NEW.tenant_id AND i.id=NEW.project_id
                   AND i.founder_id=NEW.founder_id) THEN
   RAISE EXCEPTION 'Project Founder must own follow-up';
  END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND OLD.status<>'resolved' AND NEW.status='resolved'
    AND NEW.resolved_at IS NOT NULL
    AND (to_jsonb(OLD)-'status'-'resolved_at')=(to_jsonb(NEW)-'status'-'resolved_at') THEN
  RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Follow-up evidence is immutable except resolution';
END $$;
CREATE TRIGGER ago_project_followups_guard BEFORE INSERT OR UPDATE OR DELETE
 ON ago_project_followups FOR EACH ROW EXECUTE FUNCTION ago_guard_project_followup();
