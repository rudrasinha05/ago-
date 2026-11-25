-- Intake, test and review records are permanent. A Founder removes the project
-- from the operating portfolio and closes admission to further project work.
CREATE TABLE ago_project_deletions (
 tenant_id uuid NOT NULL, project_id uuid NOT NULL, deleted_by uuid NOT NULL,
 deleted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, project_id),
 FOREIGN KEY (tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY (tenant_id,deleted_by) REFERENCES ago_users(tenant_id,id)
);
CREATE TRIGGER ago_project_deletions_immutable BEFORE UPDATE OR DELETE ON ago_project_deletions
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE FUNCTION ago_project_is_open(tenant uuid, project uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
 SELECT NOT EXISTS (SELECT 1 FROM ago_project_deletions d
                    WHERE d.tenant_id=tenant AND d.project_id=project)
$$;

CREATE FUNCTION ago_guard_deleted_project_work() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE project uuid;
BEGIN
 IF TG_TABLE_NAME IN ('ago_workspace_terminal','ago_workspace_test_runs','ago_workspace_revisions','ago_workspace_reviews') THEN
   project := NEW.project_id;
 ELSIF TG_TABLE_NAME='ago_plan_steps' THEN
   SELECT id INTO project FROM ago_founder_intakes WHERE tenant_id=NEW.tenant_id AND plan_id=NEW.plan_id;
 ELSIF TG_TABLE_NAME='ago_strategy_plans' THEN
   SELECT id INTO project FROM ago_founder_intakes WHERE tenant_id=NEW.tenant_id AND plan_id=NEW.id;
 ELSE
   SELECT i.id INTO project FROM ago_founder_intakes i JOIN ago_plan_steps s
     ON s.tenant_id=i.tenant_id AND s.plan_id=i.plan_id
     WHERE s.tenant_id=NEW.tenant_id AND s.task_id=NEW.task_id;
 END IF;
 IF project IS NOT NULL THEN
   PERFORM 1 FROM ago_founder_intakes WHERE tenant_id=NEW.tenant_id AND id=project FOR KEY SHARE;
   IF NOT ago_project_is_open(NEW.tenant_id,project) THEN
     RAISE EXCEPTION 'The Founder deleted this project' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_deleted_project_plan BEFORE UPDATE ON ago_strategy_plans
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
CREATE TRIGGER ago_deleted_project_step BEFORE INSERT OR UPDATE ON ago_plan_steps
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
CREATE TRIGGER ago_deleted_project_agent BEFORE INSERT ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
CREATE TRIGGER ago_deleted_project_terminal BEFORE INSERT ON ago_workspace_terminal
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
CREATE TRIGGER ago_deleted_project_test BEFORE INSERT ON ago_workspace_test_runs
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
CREATE TRIGGER ago_deleted_project_edit BEFORE INSERT ON ago_workspace_revisions
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
CREATE TRIGGER ago_deleted_project_qa BEFORE INSERT OR UPDATE ON ago_workspace_reviews
 FOR EACH ROW EXECUTE FUNCTION ago_guard_deleted_project_work();
