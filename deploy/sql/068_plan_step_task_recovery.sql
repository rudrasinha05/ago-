-- Authorized recovery of a failed plan-step task (issue #10).
-- A failed governed task and its agent run stay immutable evidence. Recovery
-- creates a NEW proposed task for the same step (same action and assignee),
-- records who recovered what and why, and moves the step's task link to the
-- new task. The new task still needs its own approval before any run.
CREATE TABLE ago_plan_step_task_recoveries (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 plan_id uuid NOT NULL,
 plan_step_id uuid NOT NULL,
 failed_task_id uuid NOT NULL,
 recovery_task_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 reason text NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 500),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,failed_task_id),
 UNIQUE(tenant_id,recovery_task_id),
 FOREIGN KEY (tenant_id,plan_id,plan_step_id) REFERENCES ago_plan_steps(tenant_id,plan_id,id),
 FOREIGN KEY (tenant_id,failed_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,recovery_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 CHECK (failed_task_id <> recovery_task_id)
);
CREATE INDEX ago_plan_step_task_recovery_history
 ON ago_plan_step_task_recoveries(tenant_id,plan_step_id,id);
CREATE TRIGGER ago_plan_step_task_recoveries_immutable
 BEFORE UPDATE OR DELETE ON ago_plan_step_task_recoveries
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

-- Same rules as 011, plus exactly one audited transition: on an ACTIVE plan a
-- step linked to a FAILED task may be relinked to a new PROPOSED task with the
-- step's own action and assignee, only when the matching recovery row exists.
-- Every other column must stay unchanged.
CREATE OR REPLACE FUNCTION ago_guard_plan_step() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE plan_state text;
BEGIN
 SELECT status INTO plan_state FROM ago_strategy_plans
 WHERE tenant_id=COALESCE(NEW.tenant_id,OLD.tenant_id)
   AND id=COALESCE(NEW.plan_id,OLD.plan_id);
 IF TG_OP='INSERT' AND plan_state='draft' THEN RETURN NEW; END IF;
 IF TG_OP='DELETE' AND plan_state='draft' THEN RETURN OLD; END IF;
 IF TG_OP='UPDATE' AND plan_state='active'
   AND OLD.task_id IS NULL AND NEW.task_id IS NOT NULL
   AND (OLD.id,OLD.tenant_id,OLD.plan_id,OLD.position,OLD.action,
        OLD.assignee_id,OLD.depends_on) IS NOT DISTINCT FROM
       (NEW.id,NEW.tenant_id,NEW.plan_id,NEW.position,NEW.action,
        NEW.assignee_id,NEW.depends_on) THEN
   RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND plan_state='active'
   AND OLD.task_id IS NOT NULL AND NEW.task_id IS NOT NULL
   AND OLD.task_id<>NEW.task_id
   AND (OLD.id,OLD.tenant_id,OLD.plan_id,OLD.position,OLD.action,
        OLD.assignee_id,OLD.depends_on) IS NOT DISTINCT FROM
       (NEW.id,NEW.tenant_id,NEW.plan_id,NEW.position,NEW.action,
        NEW.assignee_id,NEW.depends_on)
   AND EXISTS (SELECT 1 FROM ago_governed_tasks t
               WHERE t.tenant_id=OLD.tenant_id AND t.id=OLD.task_id AND t.status='failed')
   AND NOT EXISTS (SELECT 1 FROM ago_agent_runs r
                   WHERE r.tenant_id=OLD.tenant_id AND r.task_id=OLD.task_id AND r.status='running')
   AND EXISTS (SELECT 1 FROM ago_governed_tasks n
               WHERE n.tenant_id=NEW.tenant_id AND n.id=NEW.task_id AND n.status='proposed'
                 AND n.action=OLD.action AND n.assignee_id=OLD.assignee_id)
   AND EXISTS (SELECT 1 FROM ago_plan_step_task_recoveries v
               WHERE v.tenant_id=OLD.tenant_id AND v.plan_id=OLD.plan_id
                 AND v.plan_step_id=OLD.id AND v.failed_task_id=OLD.task_id
                 AND v.recovery_task_id=NEW.task_id) THEN
   RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Approved plans cannot be edited';
END;
$$;
